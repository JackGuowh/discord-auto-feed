"""📈 市场指标：CNN 恐惧贪婪指数（仪表盘图 + 中文解读）+ Reddit 24H 热度榜。

MARKET_MODE=fg     → 只发恐惧贪婪指数（盘前）
MARKET_MODE=close  → 恐惧贪婪指数 + Reddit 热度榜（收盘后，默认）
"""
import html
import math
import os
from datetime import datetime, timezone

import config as C
from common import ET, embed, get, now_et, post

WEBHOOK = "WEBHOOK_MARKET"

RATING_ZH = {"extreme fear": "极度恐慌", "fear": "恐慌", "neutral": "中性",
             "greed": "贪婪", "extreme greed": "极度贪婪"}
SUB_ZH = {
    "market_momentum_sp500": "市场动能",
    "stock_price_strength": "股价强度",
    "stock_price_breadth": "市场广度",
    "put_call_options": "看跌/看涨期权比",
    "market_volatility_vix": "波动率（VIX）",
    "safe_haven_demand": "避险需求",
    "junk_bond_demand": "垃圾债需求",
}
SEGMENTS = [(0, 25, "极度恐慌", "#f8b4a6"), (25, 45, "恐慌", "#fcd3c1"), (45, 55, "中性", "#e5e7eb"),
            (55, 75, "贪婪", "#cdebd3"), (75, 100, "极度贪婪", "#9fd8ad")]


def is_trading_day():
    if now_et().weekday() >= 5:
        return False
    try:
        d = get("https://query1.finance.yahoo.com/v8/finance/chart/^GSPC",
                params={"range": "1d", "interval": "1d"}).json()
        t = d["chart"]["result"][0]["meta"]["regularMarketTime"]
        return datetime.fromtimestamp(t, timezone.utc).astimezone(ET).date() == now_et().date()
    except Exception:  # noqa: BLE001
        return True


# ---------------------------------------------------------------- 恐惧贪婪指数
def gauge_html(score, rating_zh, updated):
    cx, cy, r_out, r_in = 300, 290, 250, 150

    def pt(v, r):
        a = math.pi * (1 - v / 100)
        return cx + r * math.cos(a), cy - r * math.sin(a)

    paths = []
    for lo, hi, name, color in SEGMENTS:
        active = lo <= score < hi or (hi == 100 and score >= 100)
        x1, y1 = pt(lo, r_out); x2, y2 = pt(hi, r_out)
        x3, y3 = pt(hi, r_in); x4, y4 = pt(lo, r_in)
        stroke = 'stroke="#ea580c" stroke-width="4"' if active else 'stroke="#fff" stroke-width="3"'
        fill = color if active else "#f3f4f6"
        paths.append(f'<path d="M{x1:.1f},{y1:.1f} A{r_out},{r_out} 0 0 1 {x2:.1f},{y2:.1f} '
                     f'L{x3:.1f},{y3:.1f} A{r_in},{r_in} 0 0 0 {x4:.1f},{y4:.1f} Z" fill="{fill}" {stroke}/>')
        mx, my = pt((lo + hi) / 2, (r_out + r_in) / 2)
        paths.append(f'<text x="{mx:.1f}" y="{my:.1f}" font-size="17" text-anchor="middle" '
                     f'dominant-baseline="middle" fill="{"#9a3412" if active else "#6b7280"}" '
                     f'font-weight="{700 if active else 500}">{name}</text>')
    ticks = "".join(
        f'<text x="{pt(v, r_out + 18)[0]:.1f}" y="{pt(v, r_out + 18)[1]:.1f}" font-size="14" '
        f'text-anchor="middle" fill="#9ca3af">{v}</text>' for v in (0, 25, 50, 75, 100))
    nx, ny = pt(score, r_in - 8)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;background:#fff;font-family:'Noto Sans CJK SC','Noto Sans SC',sans-serif}}
#g{{width:600px;padding:18px 0 10px;background:#fff}}
</style></head><body><div id="g">
<svg width="600" height="400" viewBox="0 0 600 400">{''.join(paths)}{ticks}
<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="#111827" stroke-width="6" stroke-linecap="round"/>
<circle cx="{cx}" cy="{cy}" r="11" fill="#111827"/>
<text x="{cx}" y="{cy + 62}" font-size="50" font-weight="800" text-anchor="middle" fill="#111827">{score:.0f}</text>
<text x="{cx}" y="{cy + 92}" font-size="19" text-anchor="middle" fill="#ea580c" font-weight="700">{rating_zh}</text>
</svg>
<div style="text-align:center;color:#9ca3af;font-size:13px">CNN Fear &amp; Greed Index · 更新于 {updated}</div>
</div></body></html>"""


def cnn_gauge_screenshot():
    """直接截取 CNN 官网的恐惧贪婪指数仪表盘（和 CNN 网页上一模一样）。"""
    from playwright.sync_api import sync_playwright
    from common import UA
    from jobs.weekly import launch
    with sync_playwright() as p:
        b = launch(p)
        try:
            page = b.new_page(viewport={"width": 1280, "height": 1400},
                              device_scale_factor=2, user_agent=UA)
            page.goto("https://www.cnn.com/markets/fear-and-greed",
                      wait_until="domcontentloaded", timeout=60000)
            sel = ".market-tabbed-container .market-fng-gauge"
            page.wait_for_selector(sel + " .market-fng-gauge__dial-number-value", timeout=30000)
            page.add_style_tag(content=(
                ".market-fng-gauge__historical{display:none!important}"
                "#onetrust-consent-sdk,[id*=onetrust],[class*=ad-slot],[class*=ad-feedback]{display:none!important}"))
            page.wait_for_timeout(2500)  # 等指针动画结束
            # 隐藏隐私同意弹窗、悬浮广告等所有浮层（fixed / sticky 元素和 iframe）
            page.evaluate("""() => {
              for (const el of document.querySelectorAll('body *')) {
                const cs = getComputedStyle(el);
                if (cs.position === 'fixed' || cs.position === 'sticky' || el.tagName === 'IFRAME')
                  el.style.setProperty('display', 'none', 'important');
              }
              document.documentElement.style.overflow = 'auto';
              document.body.style.overflow = 'auto';
            }""")
            page.wait_for_timeout(300)
            el = page.locator(sel).first
            el.scroll_into_view_if_needed()
            return el.screenshot(type="png")
        finally:
            b.close()


def render_gauge(score, rating_zh, updated):
    from playwright.sync_api import sync_playwright
    from jobs.weekly import launch
    with sync_playwright() as p:
        b = launch(p)
        try:
            page = b.new_page(viewport={"width": 600, "height": 400}, device_scale_factor=2)
            page.set_content(gauge_html(score, rating_zh, updated), wait_until="load")
            return page.locator("#g").screenshot(type="png")
        finally:
            b.close()


def fear_greed_text(d):
    fg = d["fear_and_greed"]
    score, prev = fg["score"], fg["previous_close"]
    rating = RATING_ZH.get(fg["rating"], fg["rating"])
    diff = score - prev
    move = "持平" if abs(diff) < 0.5 else (f"上升 {diff:.1f}" if diff > 0 else f"下降 {abs(diff):.1f}")
    groups = {}
    for key, name in SUB_ZH.items():
        sub = d.get(key) or {}
        if sub.get("rating"):
            groups.setdefault(RATING_ZH.get(sub["rating"], sub["rating"]), []).append(name)
    order = ["极度恐慌", "恐慌", "中性", "贪婪", "极度贪婪"]
    parts = [f"{'、'.join(groups[k])}处于{k}" for k in order if k in groups]
    text = (f"恐惧贪婪指数报 **{score:.0f}**（{rating}），较前一交易日{move}。\n"
            + ("七项分项指标中，" + "；".join(parts) + "。\n" if parts else "")
            + f"一周前 {fg['previous_1_week']:.0f} · 一个月前 {fg['previous_1_month']:.0f} · "
              f"一年前 {fg['previous_1_year']:.0f}")
    return score, rating, text


def post_fear_greed():
    d = get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata").json()
    score, rating, text = fear_greed_text(d)
    ts = datetime.fromisoformat(d["fear_and_greed"]["timestamp"]).astimezone(ET)
    updated = ts.strftime("%m/%d %H:%M ET")
    files = None
    try:
        files = [("fear_greed.png", cnn_gauge_screenshot())]
    except Exception as e:  # noqa: BLE001
        print(f"[market] CNN 截图失败，改用自绘仪表盘: {e}")
        try:
            files = [("fear_greed.png", render_gauge(score, rating, updated))]
        except Exception as e2:  # noqa: BLE001
            print(f"[market] 仪表盘图生成失败，只发文字: {e2}")
    post(WEBHOOK, files=files, embeds=[embed(
        title="😱 恐惧贪婪指数", description=text, color=0xEA580C,
        image="attachment://fear_greed.png" if files else None,
        footer="数据：CNN Fear & Greed Index · 仅供参考，不构成投资建议",
    )])


# ---------------------------------------------------------------- Reddit 热度榜
def post_reddit_hot():
    d = get("https://apewisdom.io/api/v1.0/filter/all-stocks/page/1").json()
    rows = d.get("results", [])[: C.REDDIT_TOP_N]
    lines = []
    for r in rows:
        rank = int(r["rank"])
        prev = r.get("rank_24h_ago")
        if prev in (None, "", 0):
            chg = "NEW"
        else:
            delta = int(prev) - rank
            chg = f"▲{delta}" if delta > 0 else (f"▼{-delta}" if delta < 0 else "–")
        name = html.unescape(r.get("name") or "")
        name = name if len(name) <= 14 else name[:13] + "."
        lines.append(f"`{chg:>4} {rank:02d}.` **${r['ticker']}** ({name}) 提及 `{r['mentions']}` 次")
    today = now_et()
    post(WEBHOOK, embeds=[embed(
        title=f"🔥 Reddit 24H 热度榜（{today.month}月{today.day}日）",
        description="\n".join(lines) or "暂无数据", color=0xFF4500,
        footer="数据：ApeWisdom（统计 r/wallstreetbets 等股票版块提及次数）· ▲▼ 为 24 小时排名变化",
    )])


def main():
    mode = os.getenv("MARKET_MODE", "close")
    force = os.getenv("FORCE", "0") == "1"
    # 盘前时段指数还没有当天数据，只判断是否周末
    if not force and (now_et().weekday() >= 5 or (mode == "close" and not is_trading_day())):
        print("[market] 今天不是交易日，跳过")
        return
    try:
        post_fear_greed()
    except Exception as e:  # noqa: BLE001
        print(f"[market] 恐惧贪婪指数失败: {e}")
    if mode == "close":
        try:
            post_reddit_hot()
        except Exception as e:  # noqa: BLE001
            print(f"[market] Reddit 热度榜失败: {e}")


if __name__ == "__main__":
    main()
