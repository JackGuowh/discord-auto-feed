"""⚡ 突发新闻 · 富途牛牛 7×24 快讯：只推带美股代码（.US）的快讯，附相关股票实时涨跌幅；
相关美股大涨大跌或内容里有"跳水/拉升"等词的，标为「异动直击」。"""
import re
from datetime import datetime, timezone

import config as C
from common import embed, get, load_state, post, save_state
from jobs.news import pick_new
from jobs.telegram import is_duplicate_zh

WEBHOOK = "WEBHOOK_NEWS"
MOVE_WORDS = re.compile(r"跳水|拉升|直线|涨超|跌超|暴涨|暴跌|大涨|大跌|闪崩|飙升|急跌|急涨|涨停|跌停|异动")


def fetch():
    d = get("https://news.futunn.com/news-site-api/main/get-flash-list",
            params={"pageSize": 50},
            headers={"Referer": "https://news.futunn.com/main/live", "Accept": "application/json"}).json()
    return (d.get("data") or {}).get("data", {}).get("news") or []


def pct(s):
    try:
        return float(str(s).replace("%", "").replace("+", ""))
    except ValueError:
        return None


def run(state):
    if not C.FUTU_NEWS:
        return
    try:
        items = fetch()
    except Exception as e:  # noqa: BLE001
        print(f"[futu] 获取失败: {e}")
        return
    pairs = [(f"futu:{n.get('id') or n.get('newsUniqueId')}", n) for n in items]
    new = pick_new(state, "futu", pairs)
    sent = 0
    for _, n in new:
        text = re.sub(r"\s+", " ", (n.get("content") or n.get("title") or "")).strip()
        us = [q for q in (n.get("quote") or []) if str(q.get("code", "")).endswith(".US")]
        # 正文里的美股代码，如 Coreweave(CRWV.O)、甲骨文(ORCL.N)
        seen = {q["code"][:-3] for q in us}
        for t in re.findall(r"[(（]([A-Z]{1,5})\.(?:O|N|A|US)[)）]", text):
            if t not in seen:
                us.append({"code": t + ".US", "name": "", "changeRatio": ""})
                seen.add(t)
        if not us and not re.search(r"美股|纳指|纳斯达克|标普|道指|美联储|华尔街", text):
            continue  # 只要美股相关
        if not text or is_duplicate_zh(state, text):
            continue
        sent += 1
        moves = [(q, pct(q.get("changeRatio"))) for q in us]
        big = any(p is not None and abs(p) >= C.FUTU_MOVE_PCT for _, p in moves)
        hot = big or bool(MOVE_WORDS.search(text))
        tags = []
        for q, p in moves[:4]:
            arrow = "📈" if (p or 0) > 0 else ("📉" if (p or 0) < 0 else "➖")
            tags.append(f"{arrow} ${q['code'][:-3]} {q.get('name', '')} {q.get('changeRatio', '')}".strip())
        ts = None
        try:
            ts = datetime.fromtimestamp(int(n.get("time")), timezone.utc).isoformat()
        except (TypeError, ValueError):
            pass
        post(WEBHOOK, embeds=[embed(
            title="⚡ 异动直击" if hot else None,
            description=text[:3500] + ("\n\n" + " · ".join(tags) if tags else ""),
            url=n.get("detailUrl") or None,
            color=0xF59E0B if hot else 0x2B2D31, timestamp=ts,
            footer="来源：富途牛牛 7×24（涨跌幅为推送时行情）",
        )])
    if new:
        _log(len(items), len(new), sent)


def _log(n_all, n_new, n_sent):
    print(f"[futu] 获取 {n_all} 条，新 {n_new} 条，推送 {n_sent} 条")


def main():
    state = load_state()
    try:
        run(state)
    finally:
        save_state(state)


if __name__ == "__main__":
    main()
