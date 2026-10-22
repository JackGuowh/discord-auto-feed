"""📈 市场指标：每个交易日收盘后推送主要指数、VIX、恐贪指数、重点个股。"""
import config as C
from common import embed, get, now_et, post

WEBHOOK = "WEBHOOK_MARKET"

FG_RATING = {"extreme fear": "极度恐慌 😱", "fear": "恐慌 😨", "neutral": "中性 😐",
             "greed": "贪婪 😏", "extreme greed": "极度贪婪 🤑"}


def quote(symbol):
    """返回 (最新价, 涨跌幅%)，失败返回 None。"""
    try:
        d = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={"range": "5d", "interval": "1d"}).json()
        res = d["chart"]["result"][0]
        closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
        price = res["meta"].get("regularMarketPrice") or closes[-1]
        prev = closes[-2] if len(closes) >= 2 else res["meta"].get("chartPreviousClose")
        return price, (price / prev - 1) * 100 if prev else 0.0
    except Exception as e:  # noqa: BLE001
        print(f"[market] {symbol} 失败: {e}")
        return None


def arrow(pct):
    return "🟢" if pct > 0 else ("🔴" if pct < 0 else "⚪")


def fmt_price(sym, p):
    if sym == "^TNX":
        return f"{p:.3f}%"
    return f"{p:,.2f}"


def fear_greed():
    try:
        d = get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata").json()
        fg = d["fear_and_greed"]
        return fg
    except Exception as e:  # noqa: BLE001
        print(f"[market] 恐贪指数失败: {e}")
        return None


def is_trading_day():
    """简单判断：周末不推；指数今天没有新数据（节假日）也不推。"""
    if now_et().weekday() >= 5:
        return False
    try:
        d = get("https://query1.finance.yahoo.com/v8/finance/chart/^GSPC",
                params={"range": "1d", "interval": "1d"}).json()
        from datetime import datetime, timezone
        t = d["chart"]["result"][0]["meta"]["regularMarketTime"]
        last = datetime.fromtimestamp(t, timezone.utc).astimezone(now_et().tzinfo)
        return last.date() == now_et().date()
    except Exception:  # noqa: BLE001
        return True


def main():
    import os
    if os.getenv("FORCE", "0") != "1" and not is_trading_day():
        print("[market] 今天不是交易日，跳过")
        return

    lines = []
    for sym, name in C.MARKET_SYMBOLS:
        q = quote(sym)
        if q:
            p, pct = q
            lines.append(f"{arrow(pct)} **{name}**　{fmt_price(sym, p)}　({pct:+.2f}%)")

    stocks = []
    for sym in C.WATCHLIST:
        q = quote(sym)
        if q:
            p, pct = q
            stocks.append(f"{arrow(pct)} {sym} {p:,.2f} ({pct:+.2f}%)")

    fields = []
    fg = fear_greed()
    if fg:
        score = round(fg["score"])
        rating = FG_RATING.get(fg.get("rating", ""), fg.get("rating", ""))
        bar = "█" * (score // 10) + "░" * (10 - score // 10)
        fields.append(("CNN 恐惧贪婪指数",
                       f"**{score}** {rating}\n`{bar}`\n"
                       f"昨日 {round(fg['previous_close'])} · 一周前 "
                       f"{round(fg['previous_1_week'])} · 一月前 {round(fg['previous_1_month'])}"))
    if stocks:
        fields.append(("重点个股", "\n".join(stocks)))

    today = now_et().strftime("%Y-%m-%d")
    wd = "一二三四五六日"[now_et().weekday()]
    post(WEBHOOK, embeds=[embed(
        title=f"📈 美股收盘指标 · {today}（周{wd}）",
        description="\n".join(lines) or "数据获取失败",
        fields=fields, color=0x00897B,
        footer="数据：Yahoo Finance / CNN · 仅供参考，不构成投资建议",
    )])


if __name__ == "__main__":
    main()
