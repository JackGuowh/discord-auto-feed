"""🗓️ 展会日历：根据 trade_shows.json，在展会前约 6 个月、3 个月、1 个月、1 周自动提醒；
每月 1 号推一次未来 12 个月的展会总表。第一次运行时先推一份完整总表。"""
import json
import os
from datetime import date

import config as C
from common import ROOT, embed, load_state, now_et, post, save_state

WEBHOOK = "WEBHOOK_SHOWS"
MILESTONES = [(180, "约 6 个月"), (90, "约 3 个月"), (30, "约 1 个月"), (7, "1 周")]
WD = "一二三四五六日"


def load_shows():
    data = json.loads((ROOT / "trade_shows.json").read_text(encoding="utf-8"))
    shows = []
    for s in data["shows"]:
        s = dict(s)
        s["_start"] = date.fromisoformat(s["start"])
        s["_end"] = date.fromisoformat(s["end"])
        shows.append(s)
    return sorted(shows, key=lambda s: s["_start"])


def when(s):
    a, b = s["_start"], s["_end"]
    if a.year == b.year and a.month == b.month:
        return f"{a.year}年{a.month}月{a.day}–{b.day}日"
    if a.year == b.year:
        return f"{a.year}年{a.month}月{a.day}日–{b.month}月{b.day}日"
    return f"{a:%Y-%m-%d} – {b:%Y-%m-%d}"


def detail(s, days):
    place = s["city"] + (f"（{s['venue']}）" if s.get("venue") else "")
    return (f"📅 {when(s)}（还有 {days} 天）\n📍 {place}\n💵 {s['fee']}\n"
            f"🧪 {s['gases']}\n💡 {s['why']}\n🔗 [官网]({s['url']})")


def post_overview(shows, today, title):
    rows = [(s, (s["_start"] - today).days) for s in shows if 0 <= (s["_start"] - today).days <= 400]
    if not rows:
        return
    chunks = [rows[i:i + 6] for i in range(0, len(rows), 6)]
    for n, chunk in enumerate(chunks, 1):
        fields = []
        for s, d in chunk:
            urgent = " ⚠️ 不足半年" if d < 180 else ""
            fields.append((f"{s['name']}｜{s['category']}{urgent}", detail(s, d)))
        post(WEBHOOK, embeds=[embed(
            title=f"{title}（{n}/{len(chunks)}）" if len(chunks) > 1 else title,
            fields=fields, color=0x7C3AED,
            footer=f"信息核实于 {chunks[0][0][0].get('verified', '')} · 费用为每人参会费，不含差旅和展位 · 以官网为准",
        )])


def run(state):
    from common import DRY_RUN
    if not DRY_RUN and not os.getenv(WEBHOOK):
        return
    today = now_et().date()
    if state.get("shows_last_day") == today.isoformat():
        return
    if now_et().hour < 9 and "shows_init" in state:  # 美东早上 9 点后再推
        return
    state["shows_last_day"] = today.isoformat()
    shows = load_shows()
    sent = set(state.get("shows_sent", []))

    if "shows_init" not in state:
        post_overview(shows, today, "🗓️ 展会日历总表（未来 12 个月）")
        # 已经错过的提醒节点直接标记为已发，避免一次刷屏
        for s in shows:
            d = (s["_start"] - today).days
            for m, _ in MILESTONES:
                if d < m:
                    sent.add(f"{s['name']}|{m}")
        state["shows_init"] = today.isoformat()
    elif today.day == 1:
        post_overview(shows, today, f"🗓️ {today.month}月展会日历总表（未来 12 个月）")

    for s in shows:
        d = (s["_start"] - today).days
        if d < 0:
            continue
        for m, label in sorted(MILESTONES):  # 从最近的节点找起（7 → 30 → 90 → 180）
            key = f"{s['name']}|{m}"
            if d > m:
                continue
            if key in sent:
                break
            if True:
                post(WEBHOOK, embeds=[embed(
                    title=f"⏰ 展会提醒：还有{label}｜{s['name']}",
                    description=detail(s, d)
                    + ("\n\n👉 现在可以决定是否参加，并留意早鸟价截止日期。" if m == 180 else "")
                    + ("\n\n👉 记得订机票酒店、准备样品资料和名片。" if m == 30 else ""),
                    color=0xF59E0B if m >= 90 else 0xDC2626,
                    footer="费用为每人参会费，不含差旅和展位 · 以官网为准",
                )])
                # 同一展会一次只发最近的一个节点，较远的节点一起标记
                for m2, _ in MILESTONES:
                    if m2 >= m:
                        sent.add(f"{s['name']}|{m2}")
                break
    state["shows_sent"] = sorted(sent)[-500:]


def main():
    state = load_state()
    try:
        run(state)
    finally:
        save_state(state)


if __name__ == "__main__":
    main()
