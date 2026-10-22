"""🚀 异动榜：开盘前推「盘前异动」，收盘后推「盘后异动」（涨跌幅最大的美股，市值 ≥ 20 亿美元）。
数据：Yahoo Finance（活跃股 / 涨幅榜 / 跌幅榜 + 当天发财报的热门公司）。"""
import os

import config as C
from common import embed, get, now_et, post

WEBHOOK = "WEBHOOK_MOVERS"


def screener(scr, count=100):
    d = get("https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved",
            params={"scrIds": scr, "count": count}).json()
    return d["finance"]["result"][0]["quotes"]


def chart_quote(t):
    d = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{t}",
            params={"range": "1d", "interval": "1m", "includePrePost": "true"}).json()
    res = d["chart"]["result"][0]
    closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
    base = res["meta"].get("regularMarketPrice")
    if not closes or not base:
        return None
    return {"symbol": t, "price": closes[-1], "pct": (closes[-1] / base - 1) * 100,
            "name": res["meta"].get("shortName") or t, "mcap": None}


def earnings_tickers():
    try:
        from jobs.earnings import caldata
        return [r["ticker"] for r in caldata(now_et().date())[:40]]
    except Exception as e:  # noqa: BLE001
        print(f"[movers] 今日财报列表获取失败: {e}")
        return []


def collect(mode):
    pkey, ckey = (("preMarketPrice", "preMarketChangePercent") if mode == "pre"
                  else ("postMarketPrice", "postMarketChangePercent"))
    found = {}
    for scr in ("most_actives", "day_gainers", "day_losers"):
        try:
            for q in screener(scr):
                if q.get(ckey) is None or q.get(pkey) is None:
                    continue
                if (q.get("marketCap") or 0) < C.MOVERS_MIN_MARKET_CAP:
                    continue
                found[q["symbol"]] = {"symbol": q["symbol"], "price": q[pkey], "pct": q[ckey],
                                      "name": q.get("displayName") or q.get("shortName") or q["symbol"],
                                      "mcap": q.get("marketCap")}
        except Exception as e:  # noqa: BLE001
            print(f"[movers] {scr} 获取失败: {e}")
    er = earnings_tickers()
    for t in er:
        if t in found:
            continue
        try:
            q = chart_quote(t)
            if q:
                found[t] = q
        except Exception:  # noqa: BLE001
            pass
    return list(found.values()), set(er)


def fmt(rows, er):
    out = []
    for i, r in enumerate(rows, 1):
        name = r["name"] if len(r["name"]) <= 14 else r["name"][:13] + "."
        tag = " 📊" if r["symbol"] in er else ""
        out.append(f"`{i:02d}. {r['pct']:+6.2f}%` **${r['symbol']}** ({name}) ${r['price']:,.2f}{tag}")
    return "\n".join(out) or "暂无"


def main():
    mode = os.getenv("MOVERS_MODE") or ("pre" if now_et().hour < 12 else "post")
    if os.getenv("FORCE", "0") != "1" and now_et().weekday() >= 5:
        print("[movers] 周末跳过")
        return
    rows, er = collect(mode)
    rows = [r for r in rows if abs(r["pct"]) >= 1]
    ups = sorted([r for r in rows if r["pct"] > 0], key=lambda r: -r["pct"])[: C.MOVERS_TOP_N]
    downs = sorted([r for r in rows if r["pct"] < 0], key=lambda r: r["pct"])[: C.MOVERS_TOP_N]
    label = "盘前" if mode == "pre" else "盘后"
    today = now_et()
    post(WEBHOOK, embeds=[
        embed(title=f"🚀 {label}涨幅榜（{today.month}月{today.day}日）", description=fmt(ups, er),
              color=0x16A34A),
        embed(title=f"📉 {label}跌幅榜（{today.month}月{today.day}日）", description=fmt(downs, er),
              color=0xDC2626,
              footer="📊 = 今天发布财报 · 市值 ≥ 20 亿美元 · 数据：Yahoo Finance（可能有 15 分钟延迟）"),
    ])


if __name__ == "__main__":
    main()
