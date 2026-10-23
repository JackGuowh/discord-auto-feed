"""🎯 期权频道（数据全部免费）：
1. 异常期权大单：盘中每 30 分钟扫描热门股票的期权链，成交量远超未平仓量、成交额大的合约就推送。
2. 每日期权情绪：收盘后推看跌/看涨比（Put/Call Ratio）、VIX 期限结构、今天最活跃的期权。
3. 每周一：本周发财报公司的期权预期波动（Expected Move）+ SPY/QQQ 本周到期的最大痛点和关键价位。
数据：Cboe 延迟行情（期权链，约 15 分钟延迟）、Cboe 每日市场统计、Yahoo Finance（VIX）、Earnings Whispers（财报日历）。
"""
import os
import re
import time
from datetime import date, timedelta

import config as C
from common import embed, get, load_state, now_et, post, save_state

WEBHOOK = "WEBHOOK_OPTIONS"
SYM = re.compile(r"^(.+?)(\d{6})([CP])(\d{8})$")


# ---------------- 数据 ----------------
def chain(ticker):
    """Cboe 期权链：返回 (现价, iv30, [合约...])。指数用 _SPX 这种写法。"""
    d = get(f"https://cdn.cboe.com/api/global/delayed_quotes/options/{ticker}.json", timeout=30).json()["data"]
    out = []
    for o in d.get("options", []):
        m = SYM.match(o.get("option", ""))
        if not m:
            continue
        y, mo, dd = int(m.group(2)[:2]), int(m.group(2)[2:4]), int(m.group(2)[4:])
        bid, ask, last = o.get("bid") or 0, o.get("ask") or 0, o.get("last_trade_price") or 0
        mid = (bid + ask) / 2 if bid and ask else last
        out.append({"exp": date(2000 + y, mo, dd), "cp": m.group(3), "k": int(m.group(4)) / 1000,
                    "vol": o.get("volume") or 0, "oi": o.get("open_interest") or 0,
                    "iv": o.get("iv") or 0, "mid": mid, "last": last, "delta": o.get("delta") or 0})
    return d.get("current_price") or d.get("close"), d.get("iv30"), out


def cboe_ratios():
    html = get("https://www.cboe.com/markets/us/options/market-statistics/daily").text
    pairs = re.findall(r'\\"name\\":\\"([A-Z0-9 +()/]+?PUT/CALL RATIO)\\",\\"value\\":\\"([\d.]+)\\"', html)
    return {n: float(v) for n, v in pairs}


def yahoo_last(sym):
    d = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
            params={"range": "5d", "interval": "1d"}).json()["chart"]["result"][0]
    closes = [c for c in d["indicators"]["quote"][0]["close"] if c is not None]
    return d["meta"].get("regularMarketPrice") or closes[-1], (closes[-2] if len(closes) > 1 else None)


def money(v):
    return f"${v / 1e6:.1f}M" if v >= 1e6 else f"${v / 1e3:.0f}K"


def contract_name(t, o):
    return f"${t} {o['exp']:%m/%d} ${o['k']:g} {'Call' if o['cp'] == 'C' else 'Put'}"


# ---------------- 1. 异常期权大单 ----------------
def run_flow(state):
    seen = set(state.get("opt_flow", []))
    today = now_et().date()
    hits = []
    for t in C.OPTIONS_WATCHLIST:
        try:
            px, _, opts = chain(t)
        except Exception as e:  # noqa: BLE001
            print(f"[options] {t} 期权链失败: {e}")
            continue
        for o in opts:
            days = (o["exp"] - today).days
            if days > C.OPTIONS_FLOW_MAX_DAYS or days < C.OPTIONS_FLOW_MIN_DAYS:  # 跳过快到期的末日期权
                continue
            prem = o["vol"] * (o["last"] or o["mid"]) * 100
            if (o["vol"] < C.OPTIONS_FLOW_MIN_VOLUME or prem < C.OPTIONS_FLOW_MIN_PREMIUM
                    or o["vol"] < o["oi"] * C.OPTIONS_FLOW_VOL_OI):
                continue
            key = f"{today}:{t}:{o['exp']}:{o['cp']}:{o['k']}"
            if key in seen:
                continue
            hits.append((prem, t, px, o, key))
    hits.sort(key=lambda x: -x[0])
    for prem, t, px, o, key in hits[: C.OPTIONS_FLOW_MAX_POSTS]:
        call = o["cp"] == "C"
        otm = (o["k"] - px) / px * 100 if px else 0
        days = (o["exp"] - today).days
        desc = (f"有人刚刚买卖了 **{o['vol']:,} 张** {contract_name(t, o)}，成交额约 **{money(prem)}**。\n"
                f"这个合约原本未平仓只有 {o['oi']:,} 张，今天成交是它的 **{o['vol'] / max(o['oi'], 1):.1f} 倍**，"
                f"大概率是新开的仓位。\n\n"
                f"现价 ${px:,.2f} · 行权价{'高' if otm > 0 else '低'}于现价 {abs(otm):.1f}% · "
                f"{days} 天后到期 · 隐含波动率 {o['iv'] * 100:.0f}%")
        post(WEBHOOK, embeds=[embed(
            title=f"{'🟢' if call else '🔴'} 异常期权：{contract_name(t, o)}",
            description=desc, color=0x16A34A if call else 0xDC2626,
            footer="数据：Cboe 延迟行情（约 15 分钟）· 成交量为当天累计，无法区分买方还是卖方",
        )])
        seen.add(key)
    state["opt_flow"] = sorted(seen)[-400:]


# ---------------- 2. 每日期权情绪 ----------------
def run_daily(state):
    lines = []
    try:
        r = cboe_ratios()
        eq, tot, idx = r.get("EQUITY PUT/CALL RATIO"), r.get("TOTAL PUT/CALL RATIO"), r.get("INDEX PUT/CALL RATIO")
        mood = ("偏恐慌（买看跌保护的多）" if eq and eq >= 0.8 else
                "偏贪婪（买看涨的多）" if eq and eq <= 0.5 else "中性")
        lines.append(f"**看跌/看涨比（Put/Call Ratio）**\n股票期权 **{eq}** → {mood}\n"
                     f"全市场 {tot} · 指数期权 {idx}")
    except Exception as e:  # noqa: BLE001
        print(f"[options] Cboe 统计失败: {e}")
    try:
        v, v_prev = yahoo_last("^VIX")
        v9, _ = yahoo_last("^VIX9D")
        v3m, _ = yahoo_last("^VIX3M")
        shape = ("⚠️ 倒挂（短期恐慌高于长期，市场紧张）" if v > v3m else "正常（远期高于近期，市场平稳）")
        chg = f"（{(v / v_prev - 1) * 100:+.1f}%）" if v_prev else ""
        lines.append(f"**VIX 恐慌指数** {v:.2f}{chg}\n期限结构：9 天 {v9:.2f} → 30 天 {v:.2f} → 3 个月 {v3m:.2f}\n{shape}")
    except Exception as e:  # noqa: BLE001
        print(f"[options] VIX 失败: {e}")
    act = []
    for t in C.OPTIONS_WATCHLIST:
        try:
            px, iv30, opts = chain(t)
        except Exception as e:  # noqa: BLE001
            print(f"[options] {t} 期权链失败: {e}")
            continue
        cv = sum(o["vol"] for o in opts if o["cp"] == "C")
        pv = sum(o["vol"] for o in opts if o["cp"] == "P")
        top = max(opts, key=lambda o: o["vol"], default=None)
        act.append((cv + pv, t, cv, pv, iv30, top))
        time.sleep(0.3)
    act.sort(key=lambda x: -x[0])
    if act:
        rows = []
        for i, (tv, t, cv, pv, iv30, top) in enumerate(act[:10], 1):
            pc = pv / cv if cv else 0
            rows.append(f"`{i:02d}` **${t}** {tv:,} 张 · 看跌/看涨 {pc:.2f}"
                        + (f" · IV {iv30:.0f}%" if iv30 else "")
                        + (f"\n　└ 最活跃：{contract_name(t, top)} {top['vol']:,} 张" if top else ""))
        lines.append("**今日期权成交最活跃**\n" + "\n".join(rows))
    if not lines:
        return
    post(WEBHOOK, embeds=[embed(
        title=f"📊 每日期权情绪（{now_et():%m月%d日}）", description="\n\n".join(lines), color=0x7C3AED,
        footer="数据：Cboe / Yahoo Finance · 股票期权看跌/看涨比 > 0.8 偏恐慌，< 0.5 偏贪婪（仅供参考）",
    )])


# ---------------- 3. 每周一：财报预期波动 + SPY/QQQ 关键价位 ----------------
def straddle_move(px, opts, expiry):
    strikes = sorted({o["k"] for o in opts if o["exp"] == expiry})
    if not strikes or not px:
        return None
    k = min(strikes, key=lambda s: abs(s - px))
    c = next((o for o in opts if o["exp"] == expiry and o["k"] == k and o["cp"] == "C"), None)
    p = next((o for o in opts if o["exp"] == expiry and o["k"] == k and o["cp"] == "P"), None)
    if not c or not p or not (c["mid"] and p["mid"]):
        return None
    return (c["mid"] + p["mid"]) / px * 100


def walls(lst):
    return "、".join("${:g}（{:,} 张）".format(o["k"], o["oi"]) for o in lst) or "—"


def max_pain(opts, expiry):
    sel = [o for o in opts if o["exp"] == expiry and o["oi"]]
    strikes = sorted({o["k"] for o in sel})
    if not strikes:
        return None
    def pain(s):
        return sum(o["oi"] * (max(0, s - o["k"]) if o["cp"] == "C" else max(0, o["k"] - s)) for o in sel)
    return min(strikes, key=pain)


def week_earnings(monday):
    from jobs.earnings import caldata, us_listed
    out = []
    for i in range(5):
        d = monday + timedelta(days=i)
        try:
            rows = caldata(d)
        except Exception as e:  # noqa: BLE001
            print(f"[options] 财报日历 {d} 失败: {e}")
            continue
        allow = us_listed(d)
        for r in rows:
            t = r["ticker"].upper()
            if allow is not None and t not in allow:
                continue
            out.append((d, t, r.get("releaseTime"), r.get("total") or 0))
    out.sort(key=lambda x: -x[3])
    return out[: C.OPTIONS_EM_TOP_N]


def run_weekly(state):
    today = now_et().date()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    em_store = {}
    rows = []
    for d, t, rel, _ in sorted(week_earnings(monday)):
        try:
            px, _, opts = chain(t)
        except Exception as e:  # noqa: BLE001
            print(f"[options] {t} 期权链失败: {e}")
            continue
        # 盘前发布（releaseTime=1）当天到期的合约也算；盘后发布要用第二天之后到期的
        exps = sorted({o["exp"] for o in opts if (o["exp"] >= d if rel == 1 else o["exp"] > d)})
        if not exps:
            continue
        mv = straddle_move(px, opts, exps[0])
        if mv is None:
            continue
        em_store[t] = round(mv, 1)
        when = "盘前" if rel == 1 else "盘后"
        rows.append(f"`{d:%m/%d} {when}` **${t}** ±{mv:.1f}%（约 ±${px * mv / 100:,.2f}）")
        time.sleep(0.3)
    state["opt_em"] = em_store
    embeds = []
    if rows:
        embeds.append(embed(
            title=f"🎲 本周财报 · 期权预期波动（{monday:%m/%d}–{friday:%m/%d}）",
            description="期权市场押注财报后股价会涨跌多少（平值跨式期权价格 ÷ 股价）。\n\n" + "\n".join(rows),
            color=0xF59E0B, footer="财报发布后，财报速递里会对比实际涨跌 · 数据：Cboe / Earnings Whispers",
        ))
    lv = []
    for t in ("SPY", "QQQ"):
        try:
            px, _, opts = chain(t)
        except Exception as e:  # noqa: BLE001
            print(f"[options] {t} 期权链失败: {e}")
            continue
        exps = sorted({o["exp"] for o in opts if monday <= o["exp"] <= friday})
        if not exps:
            continue
        exp = exps[-1]  # 本周五（或本周最后一个到期日）
        mp = max_pain(opts, exp)
        sel = [o for o in opts if o["exp"] == exp]
        calls = sorted([o for o in sel if o["cp"] == "C" and o["k"] > px], key=lambda o: -o["oi"])[:2]
        puts = sorted([o for o in sel if o["cp"] == "P" and o["k"] < px], key=lambda o: -o["oi"])[:2]
        coi, poi = sum(o["oi"] for o in sel if o["cp"] == "C"), sum(o["oi"] for o in sel if o["cp"] == "P")
        mv = straddle_move(px, opts, exp)
        lv.append(
            f"**${t}** 现价 ${px:,.2f}（{exp:%m/%d} 到期）\n"
            f"最大痛点 **${mp:g}** · 未平仓看跌/看涨 {poi / coi if coi else 0:.2f}"
            + (f" · 本周预期波动 ±{mv:.1f}%" if mv else "") + "\n"
            f"上方阻力（看涨未平仓最多）：{walls(calls)}\n"
            f"下方支撑（看跌未平仓最多）：{walls(puts)}")
    if lv:
        embeds.append(embed(
            title="📍 SPY / QQQ 本周期权关键价位", description="\n\n".join(lv), color=0x2563EB,
            footer="最大痛点 = 到期时让期权买方整体亏损最大的价格；未平仓量大的行权价常被当作支撑/阻力（仅供参考）",
        ))
    if embeds:
        post(WEBHOOK, embeds=embeds)


# ---------------- 调度 ----------------
def run(state):
    from common import DRY_RUN
    if not DRY_RUN and not os.getenv(WEBHOOK):
        return
    now = now_et()
    hm, wd, today = now.strftime("%H:%M"), now.weekday(), now.date().isoformat()
    if wd < 5 and "10:00" <= hm <= "16:15":
        if time.time() - state.get("opt_flow_last", 0) >= C.OPTIONS_FLOW_MINUTES * 60:
            state["opt_flow_last"] = time.time()
            run_flow(state)
    if wd < 5 and "17:30" <= hm <= "23:30" and state.get("opt_daily") != today:
        state["opt_daily"] = today
        run_daily(state)
    if wd == 0 and "08:30" <= hm <= "12:00" and state.get("opt_weekly") != today:
        state["opt_weekly"] = today
        run_weekly(state)


def main():
    state = load_state()
    try:
        run(state)
    finally:
        save_state(state)


if __name__ == "__main__":
    import sys
    s = load_state()
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        {"flow": run_flow, "daily": run_daily, "weekly": run_weekly}.get(mode, run)(s)
    finally:
        save_state(s)
