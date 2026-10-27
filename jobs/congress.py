"""🏛️ 白宫内幕：美国国会议员股票交易申报。
主数据源：Quiver Quantitative 官网公开的最新申报（和他们 X 账号推文同源）；备用：Capitol Trades。"""
import ast
import re
import time
from datetime import datetime

from bs4 import BeautifulSoup

import config as C
from common import embed, get, load_state, post, save_state
from jobs.news import pick_new

WEBHOOK = "WEBHOOK_WHITEHOUSE"
PARTY = {"Republican": "共和党", "Democrat": "民主党", "Other": "无党派"}
CHAMBER = {"House": "众议员", "Senate": "参议员"}
SIDE = {"buy": ("买入", 0x16A34A, "🟢"), "sell": ("卖出", 0xDC2626, "🔴"),
        "exchange": ("交换", 0x6B7280, "⚪"), "receive": ("获得", 0x6B7280, "⚪")}


def leaves(td):
    return [e.get_text(strip=True) for e in td.find_all(True) if not e.find(True) and e.get_text(strip=True)]


def fetch_trades():
    html = get("https://www.capitoltrades.com/trades", params={"pageSize": 48}).text
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tr in soup.select("table tbody tr"):
        tds = tr.find_all("td")
        if len(tds) < 9:
            continue
        link = tr.find("a", href=lambda h: h and "/trades/" in h)
        pol = tr.find("a", href=lambda h: h and "/politicians/" in h)
        if not link:
            continue
        p, iss = leaves(tds[0]), leaves(tds[1])
        out.append({
            "id": link["href"].rstrip("/").split("/")[-1],
            "name": p[0] if p else "",
            "party": p[1] if len(p) > 1 else "",
            "chamber": p[2] if len(p) > 2 else "",
            "state": p[3] if len(p) > 3 else "",
            "bioguide": pol["href"].rstrip("/").split("/")[-1] if pol else "",
            "issuer": iss[0] if iss else "",
            "ticker": (iss[1] if len(iss) > 1 else "N/A").replace(":US", ""),
            "traded": " ".join(leaves(tds[3])),
            "delay": "".join(x for x in leaves(tds[4]) if x.isdigit()),
            "side": " ".join(leaves(tds[6])).lower(),
            "size": " ".join(leaves(tds[7])),
            "price": " ".join(leaves(tds[8])),
        })
    return out  # 新 → 旧


QUIVER_PARTY = {"R": "共和党", "D": "民主党", "I": "无党派"}


def fetch_quiver():
    html = get("https://www.quiverquant.com/congresstrading/").text
    m = re.search(r"let recentTradesData\s*=\s*(\[.*?\]\s*\])\s*;", html, re.S)
    if not m:
        raise ValueError("页面里没找到 recentTradesData")
    raw = re.sub(r"\bNaN\b|\bnan\b", "None", m.group(1))
    out = []
    for r in ast.literal_eval(raw):
        r = list(r) + [None] * 16
        out.append({
            "id": r[11] or f"{r[5]}-{r[0]}-{r[9]}", "ticker": r[0] or "", "issuer": r[1] or "",
            "type": r[2], "side": "buy" if str(r[3]).startswith("Purchase") else
            ("sell" if str(r[3]).startswith("Sale") else str(r[3]).lower()),
            "size": r[4] or "", "name": r[13] or r[5] or "", "chamber": r[6] or "",
            "party": r[7] or "", "filed": (r[8] or "")[:10], "traded": (r[9] or "")[:10],
            "ret": r[12] if isinstance(r[12], (int, float)) else None, "photo": r[14],
            "bioguide": r[15] or "",
        })
    return out  # 新 → 旧


# ---------------- 议员所在委员会（GitHub 上公开的 unitedstates/congress-legislators 数据，免费）
COMMITTEE_ZH = {
    "Armed Services": "军事委员会", "Financial Services": "金融服务委员会", "Energy and Commerce": "能源和商务委员会",
    "Intelligence": "情报委员会", "Homeland Security": "国土安全委员会", "Foreign Affairs": "外交委员会",
    "Foreign Relations": "外交关系委员会", "Ways and Means": "筹款委员会", "Appropriations": "拨款委员会",
    "Science, Space, and Technology": "科学、太空和技术委员会", "Judiciary": "司法委员会", "Agriculture": "农业委员会",
    "Banking, Housing, and Urban Affairs": "银行、住房和城市事务委员会", "Finance": "财政委员会",
    "Commerce, Science, and Transportation": "商务、科学和交通委员会", "Energy and Natural Resources": "能源和自然资源委员会",
    "Health, Education, Labor, and Pensions": "卫生、教育、劳工和养老金委员会", "Budget": "预算委员会",
    "Transportation and Infrastructure": "交通和基础设施委员会", "Oversight and Accountability": "监督委员会",
    "Oversight and Government Reform": "监督委员会", "Natural Resources": "自然资源委员会",
    "Education and the Workforce": "教育和劳工委员会", "Veterans' Affairs": "退伍军人事务委员会",
    "Small Business": "小企业委员会", "Rules": "规则委员会", "Homeland Security and Governmental Affairs": "国土安全和政府事务委员会",
    "Environment and Public Works": "环境和公共工程委员会",
}
# 委员会 → 跟它相关的股票（议员在相关委员会还买卖这些股票，最值得关注）
COMMITTEE_STOCKS = {
    ("Armed Services", "Intelligence", "Homeland Security"): {
        "LMT", "RTX", "NOC", "GD", "BA", "LHX", "HII", "PLTR", "KTOS", "AVAV", "BWXT", "LDOS", "SAIC", "CRWD",
        "PANW", "SPCX", "RKLB", "AXON"},
    ("Energy", "Natural Resources", "Environment"): {
        "XOM", "CVX", "COP", "OXY", "EOG", "SLB", "HAL", "OKE", "KMI", "WMB", "PSX", "VLO", "MPC", "NEE", "DUK",
        "SO", "CEG", "VST", "FSLR", "ENPH", "USOU", "USO", "CCJ"},
    ("Financial Services", "Banking", "Finance", "Ways and Means"): {
        "JPM", "BAC", "WFC", "C", "GS", "MS", "SCHW", "BLK", "AXP", "COIN", "HOOD", "SOFI", "PYPL", "V", "MA", "MSTR"},
    ("Science", "Commerce"): {
        "NVDA", "AMD", "INTC", "MU", "AVGO", "TSM", "AAPL", "MSFT", "GOOGL", "META", "AMZN", "TSLA", "SPCX", "ORCL"},
    ("Health",): {"UNH", "PFE", "LLY", "MRK", "JNJ", "ABBV", "CVS", "CI", "HUM", "MRNA", "NVO"},
}
_COMMITTEES = None


def committees_of(bioguide):
    """议员 bioguide 编号 → 所在的主委员会名称（英文）。"""
    global _COMMITTEES
    if _COMMITTEES is None:
        _COMMITTEES = {}
        try:
            base = "https://theunitedstates.io/congress-legislators/"
            names = {c["thomas_id"]: re.sub(r"^(House|Senate)( Select| Permanent Select)? Committee on (the )?", "",
                                             c["name"]).strip()
                     for c in get(base + "committees-current.json", timeout=30).json()}
            for cid, members in get(base + "committee-membership-current.json", timeout=30).json().items():
                if cid in names:  # 只要主委员会，不要小组委员会
                    for m in members:
                        _COMMITTEES.setdefault(m.get("bioguide"), []).append(names[cid])
        except Exception as e:  # noqa: BLE001
            print(f"[congress] 委员会数据获取失败: {e}")
    return _COMMITTEES.get(bioguide, [])


def relevant_committee(comms, ticker):
    for keys, stocks in COMMITTEE_STOCKS.items():
        if ticker in stocks:
            for c in comms:
                if any(k in c for k in keys):
                    return c
    return None


def upper_amount(size):
    nums = [int(x.replace(",", "")) for x in re.findall(r"\$([\d,]+)", size or "")]
    return max(nums) if nums else 0


def money_short(v):
    return f"${v / 1e6:.1f} 百万" if v >= 1e6 else f"${v:,.0f}"


def run_quiver(state):
    trades = fetch_quiver()
    print(f"[congress] Quiver 最新申报 {len(trades)} 条")
    pairs = [(f"qv:{t['id']}", t) for t in trades]
    new = [t for _, t in pick_new(state, "congress_qv", pairs)
           if t["type"] in ("ST", "Stock") and t["ticker"] and t["ticker"] != "-"]
    # 同一议员、同一股票、同一方向的多笔申报合并成一条
    groups = {}
    for t in new:
        groups.setdefault((t["name"], t["ticker"], t["side"]), []).append(t)
    hot = set(C.EARNINGS_WATCHLIST) | set(C.OPTIONS_WATCHLIST) | set(C.CONGRESS_HOT_EXTRA)
    for (name, ticker, side), ts in groups.items():
        t = ts[0]
        total = sum(upper_amount(x["size"]) for x in ts)
        ret = next((x["ret"] for x in ts if x["ret"] is not None), None)
        bioguide = next((x.get("bioguide") for x in ts if x.get("bioguide")), "")
        comms = committees_of(bioguide) if bioguide else []
        rel = relevant_committee(comms, ticker)
        interesting = (total >= C.CONGRESS_MIN_AMOUNT or ticker in hot or rel
                       or (ret is not None and abs(ret) >= C.CONGRESS_MIN_MOVE))
        if not interesting:
            continue
        side_zh, color, dot = SIDE.get(side, (side, 0x6B7280, "⚪"))
        title = CHAMBER.get(t["chamber"], "议员")
        party = QUIVER_PARTY.get(t["party"], t["party"])
        company = t["issuer"].split(" - ")[0].title()
        n = f" {len(ts)} 笔" if len(ts) > 1 else "一笔"
        lines = [f"{title} **{name}**（{party}）刚刚申报了{n}{side_zh} **{company}（${ticker}）** 股票的交易，"
                 f"金额合计最高 **{money_short(total)}**。"]
        if rel:
            lines.append(f"⚠️ {name.split()[-1]} 是{'众议院' if t['chamber'] == 'House' else '参议院'}"
                         f"**{COMMITTEE_ZH.get(rel, rel)}**成员，而这只股票正属于该委员会监管或相关的行业。")
        elif comms:
            lines.append(f"{name.split()[-1]} 所在委员会：" + "、".join(COMMITTEE_ZH.get(c, c) for c in comms[:3]) + "。")
        trade_days = sorted({x["traded"] for x in ts if x["traded"]})
        info = [f"交易日 {trade_days[0]}" + (f" 至 {trade_days[-1]}" if len(trade_days) > 1 else ""),
                f"申报日 {t['filed']}"]
        if ret is not None:
            info.append(f"交易至今 ${ticker} {'上涨' if ret >= 0 else '下跌'} {abs(ret):.1f}%")
        post(WEBHOOK, embeds=[embed(
            title=f"{dot} 突发：国会议员{side_zh} ${ticker}" + (f"（{len(ts)} 笔）" if len(ts) > 1 else ""),
            url=f"https://www.quiverquant.com/congresstrading/politician/{name.replace(' ', '%20')}",
            description="\n\n".join(lines) + "\n\n" + " · ".join(info), color=color, image=t["photo"],
            footer="数据：Quiver Quantitative（STOCK Act 公开申报）· 委员会：unitedstates/congress-legislators",
        )])


def fmt_date(s):
    try:
        d = datetime.strptime(s.replace("Sept", "Sep"), "%d %b %Y")
        return f"{d.month}月{d.day}日"
    except ValueError:
        return s


def run(state):
    last = state.get("congress_last_check", 0)
    if time.time() - last < C.CONGRESS_CHECK_MINUTES * 60:
        return
    state["congress_last_check"] = time.time()
    try:
        return run_quiver(state)
    except Exception as e:  # noqa: BLE001
        print(f"[congress] Quiver 获取失败，改用 Capitol Trades: {e}")
    try:
        trades = fetch_trades()
        print(f"[congress] Capitol Trades {len(trades)} 条")
    except Exception as e:  # noqa: BLE001
        print(f"[congress] 获取失败: {e}")
        return
    pairs = [(f"ct:{t['id']}", t) for t in trades]
    for _, t in pick_new(state, "congress", pairs):
        ticker = t["ticker"]
        if not ticker or ticker in ("N/A", "-"):  # 只要股票（跳过国债、私人公司等）
            continue
        if C.CONGRESS_SKIP_SMALL and t["size"].startswith(("1K", "<1K", "0")):
            continue
        side_zh, color, dot = SIDE.get(t["side"], (t["side"], 0x6B7280, "⚪"))
        who = f"{CHAMBER.get(t['chamber'], '议员')}{t['name']}（{PARTY.get(t['party'], t['party'])}-{t['state']}）"
        desc = (f"{who}刚刚申报了一笔 **{side_zh}** **${ticker}**（{t['issuer']}）的交易，"
                f"金额 **${t['size']}**。")
        info = [f"交易日 {fmt_date(t['traded'])}"]
        if t["delay"]:
            info.append(f"申报延迟 {t['delay']} 天")
        if t["price"] and t["price"] != "N/A":
            info.append(f"成交价约 {t['price']}")
        post(WEBHOOK, embeds=[embed(
            title=f"{dot} 国会议员交易：{side_zh} ${ticker}",
            url=f"https://www.capitoltrades.com/trades/{t['id']}",
            description=desc + "\n" + " · ".join(info),
            color=color,
            thumbnail=(f"https://theunitedstates.io/images/congress/225x275/{t['bioguide']}.jpg"
                       if t["bioguide"] else None),
            footer="数据：Capitol Trades（国会议员 STOCK Act 公开申报）",
        )])


def main():
    state = load_state()
    try:
        run(state)
    finally:
        save_state(state)


if __name__ == "__main__":
    main()
