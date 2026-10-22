"""📅 每周预告：每周日推送两条消息
1. 下周财报：Earnings Whispers「Most Anticipated Earnings Releases」截图 + 代码列表
2. 下周财经日历：华尔街见闻财经日历筛选后，生成一张中文日历图片
"""
import html
import os
import re
from collections import defaultdict
from datetime import datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

import config as C
from common import UA, embed, get, now_et, post

WEBHOOK = "WEBHOOK_CALENDAR"
WD = "一二三四五六日"
EN_WD = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def next_monday():
    """周日运行 → 明天；其他日子运行 → 下周一。"""
    today = now_et().date()
    return today + timedelta(days=7 - today.weekday())


# ---------------------------------------------------------------- 财报
def fetch_ew(browser, monday):
    """抓取 Earnings Whispers 周历：返回 {top, sessions, png}。"""
    url = f"https://www.earningswhispers.com/calweek/{monday:%Y%m%d}"
    page = browser.new_page(viewport={"width": 1280, "height": 1800},
                            device_scale_factor=2, user_agent=UA)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".cw-logorow .cw-sr", timeout=30000)
        grid = page.locator(".calweek-grid").first
        grid.scroll_into_view_if_needed()
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(2000)
        srs = page.eval_on_selector_all(".cw-logorow .cw-sr",
                                        "els => els.map(e => e.textContent.trim())")
        desc = page.eval_on_selector_all(
            'meta[name="description"], meta[property="og:description"]',
            "els => els.map(e => e.content).join(' ')")
        # 去掉可能遮挡的浮层广告
        page.add_style_tag(content="[class*=ad-],[id*=google_ads],iframe{display:none!important}")
        png = grid.screenshot(type="png")
    finally:
        page.close()

    sessions = []  # [(date, '盘前'/'盘后', [tickers])]
    for s in srs:
        m = re.match(r"(Before the Open|After the Close),\s*(\w+),[^:]*:\s*(.*)$", s)
        if not m or m.group(2) not in EN_WD:
            continue
        d = monday + timedelta(days=EN_WD.index(m.group(2)))
        tickers = [t.strip() for t in m.group(3).split(",") if t.strip()]
        sessions.append((d, "盘前" if m.group(1).startswith("Before") else "盘后", tickers))
    top = re.findall(r"\(([A-Z][A-Z.\-]*)\)", desc)
    if not sessions:
        raise RuntimeError("Earnings Whispers 页面没有解析到财报数据")
    return {"top": top, "sessions": sessions, "png": png}


def fetch_nasdaq(monday):
    """备用：Earnings Whispers 打不开时，用 Nasdaq 财报日历（按市值排序，无图片）。"""
    sessions = []
    for i in range(5):
        d = monday + timedelta(days=i)
        try:
            rows = get("https://api.nasdaq.com/api/calendar/earnings",
                       params={"date": d.isoformat()},
                       headers={"Origin": "https://www.nasdaq.com",
                                "Referer": "https://www.nasdaq.com/"}).json()
            rows = (rows.get("data") or {}).get("rows") or []
        except Exception as e:  # noqa: BLE001
            print(f"[weekly] Nasdaq {d} 失败: {e}")
            continue

        def cap(r):
            try:
                return float(r.get("marketCap", "0").replace("$", "").replace(",", ""))
            except ValueError:
                return 0.0
        rows = sorted([r for r in rows if cap(r) >= 10e9], key=lambda r: -cap(r))
        for label, key in (("盘前", "time-pre-market"), ("盘后", "time-after-hours")):
            t = [r["symbol"] for r in rows if r.get("time") == key][:10]
            if t:
                sessions.append((d, label, t))
    return {"top": [], "sessions": sessions, "png": None}


def ordered_tickers(ew):
    seen, out = set(), []
    for t in ew["top"] + [t for _, _, ts in ew["sessions"] for t in ts]:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def post_earnings(monday, ew):
    tickers = ordered_tickers(ew)[: C.EARNINGS_MAX_TICKERS]
    files = [("earnings.png", ew["png"])] if ew.get("png") else None
    post(WEBHOOK,
         content="@everyone" if C.WEEKLY_MENTION_EVERYONE else None,
         mention_everyone=C.WEEKLY_MENTION_EVERYONE,
         files=files,
         embeds=[embed(
             title=f"📅 {monday.month}月{monday.day}日当周财报",
             description=" ".join(f"${t}" for t in tickers) or "暂无数据",
             color=0xF5A623,
             image="attachment://earnings.png" if files else None,
             footer="来源：Earnings Whispers · Most Anticipated Earnings Releases",
         )])


# ---------------------------------------------------------------- 财经日历
def fetch_calendar(monday):
    tz = ZoneInfo(C.CAL_TZ)
    start = datetime.combine(monday, dtime(0, 0), tz)
    end = start + timedelta(days=7) - timedelta(seconds=1)
    items = get("https://api-one-wscn.awtmt.com/apiv1/finance/macrodatas",
                params={"start": int(start.timestamp()), "end": int(end.timestamp())}
                ).json()["data"]["items"]
    titles = {x.get("title") for x in items}
    rows = []
    for x in items:
        imp = x.get("importance") or 1
        is_data = x.get("calendar_type") == "FD"
        title = (x.get("title") or "").strip()
        if is_data and x.get("country_id") in C.CAL_DATA_COUNTRIES:
            ok = imp >= C.CAL_DATA_MIN_IMPORTANCE
        else:
            ok = imp >= C.CAL_OTHER_MIN_IMPORTANCE
        if not ok or not title:
            continue
        # FOMC 利率上下限只保留一条
        if title.endswith("(下限)") and title.replace("(下限)", "(上限)") in titles:
            continue
        title = title.replace("FOMC利率决策(上限)", "美联储FOMC利率决议（上限）")
        dt = datetime.fromtimestamp(x["public_date"], timezone.utc).astimezone(tz)
        tbd = not is_data and dt.minute % 15 != 0  # 事件的时间不规整 = 时间待定
        if is_data and x.get("country_id") not in ("US",):
            title = f"{x.get('country', '')} {title}"
        unit = x.get("unit") or ""
        unit = unit if unit == "%" else ""
        extra = []
        if x.get("forecast"):
            extra.append(f"预期 {x['forecast']}{unit}")
        if x.get("previous"):
            extra.append(f"前值 {x['previous']}{unit}")
        rows.append({"dt": dt, "tbd": tbd, "title": title, "extra": " · ".join(extra),
                     "imp": imp, "event": not is_data})
    rows.sort(key=lambda r: (r["dt"].date(), r["tbd"], r["dt"]))
    return rows


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Noto Sans CJK SC','Noto Sans SC','Microsoft YaHei',sans-serif;background:#eef2f7;padding:24px;width:860px;color:#1f2937}
.card{background:#fff;border-radius:18px;overflow:hidden;box-shadow:0 4px 18px rgba(15,23,42,.08)}
.hd{background:linear-gradient(120deg,#1d4ed8,#2563eb 55%,#3b82f6);color:#fff;padding:26px 30px 22px}
.hd h1{font-size:34px;font-weight:900;letter-spacing:2px}
.hd .sub{margin-top:8px;font-size:17px;opacity:.92;display:flex;justify-content:space-between}
.day{display:flex;border-top:1px solid #e5e7eb}
.day .d{width:118px;flex:none;padding:16px 0 16px 22px;background:#f8fafc}
.day .d b{display:block;font-size:24px;font-weight:800;color:#1d4ed8}
.day .d span{font-size:15px;color:#64748b}
.day .list{flex:1;padding:8px 18px 10px 14px}
.r{display:flex;align-items:flex-start;padding:7px 10px;border-radius:8px;margin:2px 0;font-size:16px;line-height:1.45}
.r .t{width:58px;flex:none;color:#64748b;font-variant-numeric:tabular-nums}
.r .x{flex:1}
.r .x small{display:block;color:#94a3b8;font-size:13px}
.r.hi{background:#fff4e5}
.r.hi .x{font-weight:700;color:#b45309}
.r.hi .t{color:#d97706;font-weight:700}
.r.ev .x{color:#0f172a}
.r.er{background:#eff6ff}
.r.er .t{color:#2563eb;font-weight:700}
.r.er .x{color:#1e3a8a;font-family:'DejaVu Sans Mono',monospace;font-size:14.5px}
.ft{padding:14px 26px;font-size:13px;color:#94a3b8;border-top:1px solid #e5e7eb;display:flex;justify-content:space-between}
.lg i{display:inline-block;width:11px;height:11px;border-radius:3px;margin:0 4px 0 12px;vertical-align:-1px}
"""


def render_calendar(browser, monday, rows, ew):
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["dt"].date()].append(r)
    er_by_day = defaultdict(list)
    for d, label, ts in (ew or {}).get("sessions", []):
        er_by_day[d].append((label, ts[: C.CAL_EARNINGS_PER_DAY]))

    e = html.escape
    days_html = []
    for i in range(7):
        d = monday + timedelta(days=i)
        items = []
        for r in by_day.get(d, []):
            cls = "r" + (" hi" if r["imp"] >= C.CAL_HIGHLIGHT_IMPORTANCE else "") + (" ev" if r["event"] else "")
            t = "待定" if r["tbd"] else r["dt"].strftime("%H:%M")
            small = f"<small>{e(r['extra'])}</small>" if r["extra"] else ""
            items.append(f'<div class="{cls}"><div class="t">{t}</div><div class="x">{e(r["title"])}{small}</div></div>')
        for label, ts in er_by_day.get(d, []):
            items.append(f'<div class="r er"><div class="t">{label}</div><div class="x">{e("  ".join(ts))}</div></div>')
        if not items:
            continue
        days_html.append(f'<div class="day"><div class="d"><b>{d.month}/{d.day}</b><span>周{WD[d.weekday()]}</span></div>'
                         f'<div class="list">{"".join(items)}</div></div>')

    sunday = monday + timedelta(days=6)
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div class="card" id="cal">
 <div class="hd"><h1>下周财经日历</h1>
  <div class="sub"><span>{monday:%Y.%m.%d} – {sunday:%Y.%m.%d}</span><span>时间：{e(C.CAL_TZ_LABEL)}</span></div></div>
 {''.join(days_html) or '<div class="day"><div class="list">暂无数据</div></div>'}
 <div class="ft"><span>数据：华尔街见闻 · Earnings Whispers</span>
  <span class="lg"><i style="background:#fdba74"></i>重点<i style="background:#bfdbfe"></i>热门财报（美东日期）</span></div>
</div></body></html>"""
    page = browser.new_page(viewport={"width": 908, "height": 1200}, device_scale_factor=2)
    try:
        page.set_content(doc, wait_until="load")
        page.wait_for_timeout(300)
        return page.locator("#cal").screenshot(type="png")
    finally:
        page.close()


def post_calendar(monday, rows, png):
    sunday = monday + timedelta(days=6)
    keys = [r for r in rows if r["imp"] >= C.CAL_HIGHLIGHT_IMPORTANCE][:10]
    lines = [f"• 周{WD[r['dt'].weekday()]} {'待定' if r['tbd'] else r['dt'].strftime('%H:%M')}　{r['title']}"
             for r in keys]
    post(WEBHOOK, files=[("calendar.png", png)], embeds=[embed(
        title=f"📅 下周财经日历 · {monday.month}/{monday.day} – {sunday.month}/{sunday.day}",
        description=("**本周重点**\n" + "\n".join(lines)) if lines else None,
        color=0x2563EB, image="attachment://calendar.png",
        footer=f"数据：华尔街见闻 · 时间为{C.CAL_TZ_LABEL}",
    )])


# ---------------------------------------------------------------- main
def launch(p):
    try:
        return p.chromium.launch()
    except Exception:  # noqa: BLE001  本地沙盒环境的备用路径
        return p.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH", "/opt/pw-browsers/chromium"))


def main():
    from playwright.sync_api import sync_playwright

    monday = next_monday()
    print(f"[weekly] 目标周：{monday}")
    with sync_playwright() as p:
        browser = launch(p)
        try:
            try:
                ew = fetch_ew(browser, monday)
            except Exception as e:  # noqa: BLE001
                print(f"[weekly] Earnings Whispers 失败，改用 Nasdaq: {e}")
                ew = fetch_nasdaq(monday)
            post_earnings(monday, ew)

            try:
                rows = fetch_calendar(monday)
            except Exception as e:  # noqa: BLE001
                print(f"[weekly] 财经日历获取失败: {e}")
                rows = []
            png = render_calendar(browser, monday, rows, ew)
            post_calendar(monday, rows, png)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
