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
from jobs.zh_names import zh_name

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
        # 跳过场外交易的外国公司 ADR（5 个字母、以 Y/F 结尾，如 CAJPY），只留美股
        if t not in seen and not (len(t) == 5 and t[-1] in "YF"):
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
        if x.get("country_id") not in C.CAL_COUNTRIES:
            continue
        ok = imp >= (C.CAL_DATA_MIN_IMPORTANCE if is_data else C.CAL_EVENT_MIN_IMPORTANCE)
        if not ok or not title:
            continue
        # FOMC 利率上下限只保留一条
        if title.endswith("(下限)") and title.replace("(下限)", "(上限)") in titles:
            continue
        title = title.replace("FOMC利率决策(上限)", "美联储FOMC利率决议")
        dt = datetime.fromtimestamp(x["public_date"], timezone.utc).astimezone(tz)
        tbd = not is_data and dt.minute % 15 != 0  # 事件的时间不规整 = 时间待定
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


ET = ZoneInfo("America/New_York")
# 美股休市日（需要时补充）
US_HOLIDAYS = {"2026-11-26": "感恩节", "2026-12-25": "圣诞节", "2027-01-01": "元旦", "2027-01-18": "马丁·路德·金纪念日",
               "2027-02-15": "总统日", "2027-03-26": "耶稣受难日", "2027-05-31": "阵亡将士纪念日",
               "2027-06-18": "六月节（调休）", "2027-07-05": "独立日（调休）", "2027-09-06": "劳动节",
               "2027-11-25": "感恩节", "2027-12-24": "圣诞节（调休）"}
FED_WORDS = ("FOMC", "利率决议", "美联储主席", "鲍威尔", "议息")
DATA_WORDS = ("GDP", "PCE", "CPI", "非农", "就业报告", "失业率", "零售销售", "PPI")

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Noto Sans CJK SC','Noto Sans SC','Microsoft YaHei',sans-serif;background:#fff;width:760px;color:#1f2937}
#cal{padding:34px 34px 24px;background:#fff}
.top{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #e5e7eb;padding-bottom:14px}
.top h1{font-size:40px;font-weight:900;letter-spacing:2px;color:#111827}
.top .rg{font-size:20px;color:#475569;margin-top:6px;font-weight:600}
.top .tz{font-size:12px;color:#94a3b8;margin-top:6px}
.badge{width:64px;height:64px;border-radius:50%;background:#f97316;color:#fff;font-weight:900;font-size:26px;display:flex;align-items:center;justify-content:center}
.sec{display:flex;align-items:center;margin:22px 0 8px;font-size:22px;font-weight:800;color:#111827}
.sec:before{content:"";width:5px;height:24px;background:#2563eb;margin-right:10px;border-radius:2px}
.sec small{margin-left:auto;font-size:12px;color:#94a3b8;font-weight:400}
.day{display:flex;border-top:1px solid #eef0f3;padding:8px 6px}
.day.hl{background:#fff4e8;border-radius:6px}
.dl{width:104px;flex:none;padding-top:4px}
.dl b{font-size:22px;font-weight:900;color:#111827}
.dl span{font-size:13px;color:#475569;margin-left:4px}
.dl i{display:inline-block;margin-top:6px;background:#f97316;color:#fff;font-style:normal;font-size:12px;padding:2px 8px;border-radius:3px;font-weight:700}
.items{flex:1;border-left:2px solid #dbeafe;margin-left:4px}
.it{display:flex;align-items:flex-start;padding:4px 0 4px 16px;position:relative;font-size:14.5px;line-height:1.5}
.it:before{content:"";position:absolute;left:-7px;top:9px;width:10px;height:10px;border-radius:50%;background:#2563eb;border:2px solid #fff}
.it.k:before{background:#fff;border:3px solid #f59e0b;width:8px;height:8px}
.it .t{width:66px;flex:none;color:#475569;font-variant-numeric:tabular-nums;font-size:13.5px}
.it .x{flex:1;color:#1f2937}
.it.k .x{font-weight:800;color:#111827}
.it .x small{color:#94a3b8;font-size:12px;font-weight:400;margin-left:6px}
.wt{padding:9px 6px;border-top:1px solid #eef0f3;display:flex;font-size:14px;line-height:1.55}
.wt .n{width:34px;flex:none;color:#2563eb;font-size:20px;font-weight:700;line-height:1.1}
.wt .x b{color:#111827}
.ft{margin-top:14px;font-size:11px;color:#94a3b8;display:flex;justify-content:space-between}
"""


def build_days(monday, rows, ew, names):
    """按美东日期分组：盘前财报 → 宏观数据/事件（北京时间，跨日标 +1）→ 盘后财报。"""
    days = defaultdict(list)
    tz = ZoneInfo(C.CAL_TZ)
    for r in rows:
        bj = r["dt"].astimezone(tz)
        et = r["dt"].astimezone(ET)
        d = et.date()
        if r["tbd"]:
            label, key = "当日", 2000
        else:
            label = bj.strftime("%H:%M") + (" +1" if bj.date() > d else "")
            key = et.hour * 60 + et.minute
        key = max(key, 1)
        days[d].append({"key": key, "t": label, "x": r["title"], "small": r["extra"],
                        "k": r["imp"] >= C.CAL_HIGHLIGHT_IMPORTANCE, "kind": "macro"})
    stars = set(ordered_tickers(ew)[: C.CAL_STAR_EARNINGS]) if ew else set()
    for d, label, ts in (ew or {}).get("sessions", []):
        ts = ts[: C.CAL_EARNINGS_PER_DAY]
        if not ts:
            continue
        big = [t for t in ts if t in stars]
        txt = "、".join(zh_name(t, names.get(t, "")) for t in ts) + "财报"
        days[d].append({"key": 0 if label == "盘前" else 16 * 60, "t": label, "x": txt, "small": "",
                        "k": bool(big), "kind": "er", "tickers": ts})
    for d in days:
        days[d].sort(key=lambda x: x["key"])
    return days


def day_tag(items):
    txt = " ".join(i["x"] for i in items if i["k"])
    if any(w in txt for w in FED_WORDS):
        return "议息焦点"
    if any(w in txt for w in DATA_WORDS):
        return "数据焦点"
    return ""


def watch_points(monday, days, names):
    """市场关注：根据本周数据自动生成的要点（不做主观判断）。"""
    pts = []
    def wd(d):
        return f"周{WD[d.weekday()]}"
    fed = [(d, i) for d, its in sorted(days.items()) for i in its
           if i["kind"] == "macro" and i["k"] and any(w in i["x"] for w in FED_WORDS)]
    if fed:
        pts.append("<b>货币政策：</b>" + "；".join((f"{wd(d)}（北京时间次日 {i['t'][:5]}）{i['x']}" if "+1" in i["t"] else f"{wd(d)} {i['t']} {i['x']}") for d, i in fed[:3]) + "。")
    data = [(d, i) for d, its in sorted(days.items()) for i in its
            if i["kind"] == "macro" and i["k"] and not any(w in i["x"] for w in FED_WORDS)]
    if data:
        pts.append("<b>重磅数据：</b>" + "；".join(f"{wd(d)} {i['x']}" for d, i in data[:5]) + "。")
    big = []
    for d, its in sorted(days.items()):
        for i in its:
            if i["kind"] == "er" and i["k"]:
                big.append(f"{wd(d)}{i['t']} " + "、".join(zh_name(t, names.get(t, "")) for t in i["tickers"][:4]))
    if big:
        pts.append("<b>重点财报：</b>" + "；".join(big[:6]) + "。")
    sunday = monday + timedelta(days=6)
    hol = [f"{datetime.fromisoformat(k):%m/%d} {v}美股休市" for k, v in US_HOLIDAYS.items()
           if monday.isoformat() <= k <= sunday.isoformat()]
    if hol:
        pts.append("<b>休市提醒：</b>" + "；".join(hol) + "。")
    a = datetime.combine(monday, dtime(12), ET).utcoffset()
    for i in range(1, 8):
        dd = monday + timedelta(days=i)
        b = datetime.combine(dd, dtime(12), ET).utcoffset()
        if b != a:
            later = b < a
            pts.append(f"<b>时间调整：</b>{dd:%m/%d} 起美国{'结束' if later else '开始'}夏令时，"
                       f"美股交易和数据发布的北京时间{'推迟' if later else '提前'}一小时。")
            break
    return pts[:5]


def render_calendar(browser, monday, rows, ew, names=None):
    names = names or {}
    e = html.escape
    days = build_days(monday, rows, ew, names)
    blocks = []
    for i in range(7):
        d = monday + timedelta(days=i)
        its = days.get(d, [])
        if not its:
            continue
        tag = day_tag(its)
        li = "".join(
            f'<div class="it{" k" if x["k"] else ""}"><div class="t">{e(x["t"])}</div>'
            f'<div class="x">{e(x["x"])}{f"<small>{e(x["small"])}</small>" if x["small"] else ""}</div></div>'
            for x in its)
        blocks.append(f'<div class="day{" hl" if tag else ""}"><div class="dl"><b>{d.month}/{d.day}</b>'
                      f'<span>周{WD[d.weekday()]}</span>{f"<br><i>{tag}</i>" if tag else ""}</div>'
                      f'<div class="items">{li}</div></div>')
    pts = watch_points(monday, days, names)
    watch = "".join(f'<div class="wt"><div class="n">{n:02d}</div><div class="x">{p}</div></div>'
                    for n, p in enumerate(pts, 1))
    sunday = monday + timedelta(days=6)
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div id="cal">
 <div class="top"><div><h1>下周财经周历</h1><div class="rg">{monday:%Y.%m.%d} – {sunday:%Y.%m.%d}</div>
  <div class="tz">日期按美东交易日归类 · 时间为{e(C.CAL_TZ_LABEL)}（+1 = 北京时间次日）</div></div>
  <div class="badge">美</div></div>
 <div class="sec">重要日程<small>○ 橙色 = 重点关注</small></div>
 {''.join(blocks) or '<div class="day">暂无数据</div>'}
 {f'<div class="sec">市场关注<small>根据本周日程自动整理</small></div>{watch}' if watch else ''}
 <div class="ft"><span>数据：华尔街见闻 · Earnings Whispers</span><span>生成于 {now_et():%Y-%m-%d}</span></div>
</div></body></html>"""
    page = browser.new_page(viewport={"width": 760, "height": 1200}, device_scale_factor=2)
    try:
        page.set_content(doc, wait_until="load")
        page.wait_for_timeout(300)
        return page.locator("#cal").screenshot(type="png")
    finally:
        page.close()


def company_names(monday):
    """Earnings Whispers 日历接口：代码 → 英文公司名（用于没有中文名的公司）。"""
    from jobs.earnings import caldata
    out = {}
    for i in range(5):
        try:
            for r in caldata(monday + timedelta(days=i)):
                out[r["ticker"].upper()] = r.get("company", "")
        except Exception as e:  # noqa: BLE001
            print(f"[weekly] 公司名获取失败: {e}")
    return out


def post_calendar(monday, rows, png):
    sunday = monday + timedelta(days=6)
    post(WEBHOOK, content="@everyone" if C.WEEKLY_MENTION_EVERYONE else None,
         mention_everyone=C.WEEKLY_MENTION_EVERYONE,
         files=[("calendar.png", png)], embeds=[embed(
             title=f"📅 下周财经周历 · {monday.month}/{monday.day} – {sunday.month}/{sunday.day}",
             color=0x2563EB, image="attachment://calendar.png",
             footer=f"数据：华尔街见闻 · Earnings Whispers · 时间为{C.CAL_TZ_LABEL}",
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
            png = render_calendar(browser, monday, rows, ew, company_names(monday))
            post_calendar(monday, rows, png)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
