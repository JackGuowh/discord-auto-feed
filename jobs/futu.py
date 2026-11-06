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
    for _, n in pick_new(state, "futu", pairs):
        us = [q for q in (n.get("quote") or []) if str(q.get("code", "")).endswith(".US")]
        if not us:
            continue  # 只要美股相关
        text = re.sub(r"\s+", " ", (n.get("content") or n.get("title") or "")).strip()
        if not text or is_duplicate_zh(state, text):
            continue
        moves = [(q, pct(q.get("changeRatio"))) for q in us]
        big = any(p is not None and abs(p) >= C.FUTU_MOVE_PCT for _, p in moves)
        hot = big or bool(MOVE_WORDS.search(text))
        tags = []
        for q, p in moves[:4]:
            arrow = "📈" if (p or 0) > 0 else ("📉" if (p or 0) < 0 else "➖")
            tags.append(f"{arrow} ${q['code'][:-3]} {q.get('name', '')} {q.get('changeRatio', '')}")
        ts = None
        try:
            ts = datetime.fromtimestamp(int(n.get("time")), timezone.utc).isoformat()
        except (TypeError, ValueError):
            pass
        post(WEBHOOK, embeds=[embed(
            title="⚡ 异动直击" if hot else None,
            description=text[:3500] + "\n\n" + " · ".join(tags),
            url=n.get("detailUrl") or None,
            color=0xF59E0B if hot else 0x2B2D31, timestamp=ts,
            footer="来源：富途牛牛 7×24（涨跌幅为推送时行情）",
        )])


def main():
    state = load_state()
    try:
        run(state)
    finally:
        save_state(state)


if __name__ == "__main__":
    main()
