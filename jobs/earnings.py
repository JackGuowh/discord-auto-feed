"""📊 财报速递：热门公司一发布财报，就推送 EPS / 营收 vs 预期、同比增长和盘前/盘后股价反应。
数据：Earnings Whispers 财报日历接口（公开）+ Yahoo Finance 盘前盘后价格。"""
import time

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
        rows = caldata(today)[: C.EARNINGS_TOP_N]
    except Exception as e:  # noqa: BLE001
        print(f"[earnings] 财报日历获取失败: {e}")
        return
    reported = [r for r in rows if r.get("eps") is not None]
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
