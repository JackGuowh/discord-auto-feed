"""🏛️ 白宫内幕：美国国会议员股票交易申报（数据来自 Capitol Trades，和 Quiver Quant 推文同源的公开申报）。"""
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
        trades = fetch_trades()
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
