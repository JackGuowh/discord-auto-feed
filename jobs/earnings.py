"""📊 财报速递：热门公司一发布财报，就推送 EPS / 营收 vs 预期、同比增长和盘前/盘后股价反应。
数据：Earnings Whispers 财报日历接口（公开）+ Yahoo Finance 盘前盘后价格。"""
import time
from datetime import timedelta

import config as C
from common import embed, get, load_state, now_et, post, save_state
from jobs.news import pick_new

WEBHOOK = "WEBHOOK_EARNINGS"


def caldata(day):
    rows = get(f"https://www.earningswhispers.com/api/caldata/{day:%Y%m%d}",
               headers={"Referer": "https://www.earningswhispers.com/calendar"}).json()
    rows = rows if isinstance(rows, list) else rows.get("data", [])
    rows.sort(key=lambda r: -(r.get("total") or 0))  # total 越高 = 关注度越高
    return rows


_US_CACHE = {}


def nasdaq_caps(day):
    """Nasdaq 财报日历：当天在美国主板发布财报的公司 → 市值。失败时返回 None。"""
    key = day.isoformat()
    hit = _US_CACHE.get(key)
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    try:
        rows = get("https://api.nasdaq.com/api/calendar/earnings", params={"date": key},
                   headers={"Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}).json()
        rows = (rows.get("data") or {}).get("rows") or []
    except Exception as e:  # noqa: BLE001
        print(f"[earnings] Nasdaq 日历获取失败: {e}")
        return None

    def cap(r):
        try:
            return float(str(r.get("marketCap", "0")).replace("$", "").replace(",", "") or 0)
        except ValueError:
            return 0.0
    caps = {r["symbol"].upper(): cap(r) for r in rows}
    if rows:
        _US_CACHE[key] = (time.time(), caps)
    return caps if rows else None


def us_listed(day):
    """当天在美国主板发布财报、且市值 ≥ EARNINGS_MIN_MARKET_CAP 的公司代码。失败时返回 None。"""
    caps = nasdaq_caps(day)
    if caps is None:
        return None
    return {t for t, c in caps.items() if c >= C.EARNINGS_MIN_MARKET_CAP}


_HOT_CACHE = {}


def week_hot(day):
    """Earnings Whispers 本周「最受关注财报」：(本周前 10 名, 各时段热门榜里的全部代码)。"""
    import re
    monday = day - timedelta(days=day.weekday())
    hit = _HOT_CACHE.get(monday)
    if hit and time.time() - hit[0] < 6 * 3600:
        return hit[1]
    html_ = get(f"https://www.earningswhispers.com/calweek/{monday:%Y%m%d}").text
    m = re.search(r'name="description"\s+content="([^"]*)"', html_) or re.search(r'content="([^"]*most anticipated[^"]*)"', html_)
    top = re.findall(r"\(([A-Z][A-Z.\-]*)\)", m.group(1)) if m else []
    grid = set()
    for syms in re.findall(r'data-symbols="([^"]*)"', html_):
        grid.update(x.strip().upper() for x in syms.split(",") if x.strip())
    if not grid:
        raise ValueError("没有解析到本周热门财报榜")
    _HOT_CACHE[monday] = (time.time(), (set(top), grid))
    return set(top), grid


def is_hot(t, day):
    """只推热门股：自选股 / 本周前 10 名 / 本周热门榜上且市值 ≥ EARNINGS_HOT_MIN_CAP。"""
    t = t.upper()
    if t in C.EARNINGS_WATCHLIST:
        return True
    caps = nasdaq_caps(day) or {}
    try:
        top, grid = week_hot(day)
    except Exception as e:  # noqa: BLE001
        print(f"[earnings] 热门财报榜获取失败，改按市值筛选: {e}")
        return caps.get(t, 0) >= C.EARNINGS_HOT_MIN_CAP
    if t in top:
        return True
    return t in grid and caps.get(t, 0) >= C.EARNINGS_HOT_MIN_CAP


def looks_otc(t):
    # 场外交易的外国公司 ADR 一般是 5 个字母、以 Y 或 F 结尾（如 DNBBY、SVNLY）
    return len(t) == 5 and t[-1] in "YF"


def money(v):
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1e9:
        return f"${v / 1e9:.2f}B"
    if a >= 1e6:
        return f"${v / 1e6:.1f}M"
    return f"${v:,.0f}"


def beat(actual, est):
    if actual is None or est is None:
        return "", None
    if est == 0:
        return ("✅ 超预期" if actual > 0 else "❌ 不及预期"), None
    pct = (actual - est) / abs(est) * 100
    tag = "✅ 超预期" if actual > est else ("❌ 不及预期" if actual < est else "➖ 符合预期")
    return tag, pct


def ext_move(ticker):
    """盘前/盘后最新价相对上一收盘价的涨跌幅。"""
    try:
        d = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                params={"range": "1d", "interval": "1m", "includePrePost": "true"}).json()
        res = d["chart"]["result"][0]
        closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
        base = res["meta"].get("regularMarketPrice")
        if closes and base:
            return closes[-1], (closes[-1] / base - 1) * 100
    except Exception as e:  # noqa: BLE001
        print(f"[earnings] {ticker} 股价获取失败: {e}")
    return None


def run(state):
    import os
    from common import DRY_RUN
    if not DRY_RUN and not os.getenv(WEBHOOK):
        return  # 还没配置财报频道的 Webhook，先不消耗记录
    last = state.get("earnings_last_check", 0)
    if time.time() - last < C.EARNINGS_CHECK_MINUTES * 60:
        return
    state["earnings_last_check"] = time.time()
    today = now_et().date()
    try:
        rows = caldata(today)
    except Exception as e:  # noqa: BLE001
        print(f"[earnings] 财报日历获取失败: {e}")
        return
    reported = [r for r in rows if r.get("eps") is not None]
    reported = [r for r in reported if not looks_otc(r["ticker"]) and is_hot(r["ticker"], today)]
    pairs = [(f"er:{today}:{r['ticker']}", r) for r in reported]
    for _, r in pick_new(state, "earnings_posted", pairs):
        t = r["ticker"]
        eps, eps_est = r.get("eps"), r.get("q1EstEPS")
        rev = r["revenue"] * 1e6 if r.get("revenue") is not None else None
        rev_est = r.get("q1RevEst")
        prev_rev = r["qSales"] * 1e6 if r.get("qSales") else None
        eps_tag, eps_pct = beat(eps, eps_est)
        rev_tag, rev_pct = beat(rev, rev_est)
        lines = [
            f"**EPS**　${eps:.2f}　vs 预期 {f'${eps_est:.2f}' if eps_est is not None else '—'}　{eps_tag}"
            + (f"（{eps_pct:+.1f}%）" if eps_pct is not None else ""),
            f"**营收**　{money(rev)}　vs 预期 {money(rev_est)}　{rev_tag}"
            + (f"（{rev_pct:+.1f}%）" if rev_pct is not None else ""),
        ]
        if rev and prev_rev:
            lines.append(f"**营收同比**　{(rev / prev_rev - 1) * 100:+.1f}%")
        mv = ext_move(t)
        session = "盘前" if now_et().hour < 12 else "盘后"
        if mv:
            arrow = "🟢" if mv[1] > 0 else ("🔴" if mv[1] < 0 else "⚪")
            lines.append(f"**{session}股价**　{arrow} ${mv[0]:,.2f}（{mv[1]:+.2f}%）")
        em = (state.get("opt_em") or {}).get(t)
        if em:
            note = ""
            if mv:
                note = "，实际波动超出预期 🔥" if abs(mv[1]) > em else "，在预期范围内"
            lines.append(f"**期权预期波动**　±{em}%{note}")
        good = [x for x in (eps_pct, rev_pct) if x is not None]
        color = 0x16A34A if good and all(x > 0 for x in good) else (
            0xDC2626 if good and all(x < 0 for x in good) else 0xF59E0B)
        post(WEBHOOK, embeds=[embed(
            title=f"📊 ${t} 财报出炉｜{r.get('company', '')}",
            url=f"https://www.earningswhispers.com/epsdetails/{t}",
            description="\n".join(lines), color=color,
            thumbnail=f"https://www.earningswhispers.com/api/smallLogo/{t}",
            footer=f"财季 {r.get('qDate', '')} · 数据：Earnings Whispers / Yahoo Finance",
        )])


def main():
    state = load_state()
    try:
        run(state)
    finally:
        save_state(state)


if __name__ == "__main__":
    main()
