"""⚡ 突发新闻：华尔街见闻 7x24 中文快讯 + 中文 RSS 新闻源。"""
from datetime import datetime, timezone

import feedparser

import config as C
from common import (embed, get, load_state, post, remember, save_state,
                    strip_html, clip)

WEBHOOK = "WEBHOOK_NEWS"


def pick_new(state, key, items):
    """items: [(id, payload)]，按新→旧排列。返回需要推送的（旧→新）。"""
    seen = set(state.get(key, []))
    first_run = key not in state
    new = [(i, p) for i, p in items if i not in seen]
    if first_run:
        new = new[: C.FIRST_RUN_BACKFILL]
    remember(state, key, [i for i, _ in items])
    return list(reversed(new))


def keyword_ok(text):
    return not C.NEWS_KEYWORDS or any(k in text for k in C.NEWS_KEYWORDS)


def run_wscn(state):
    for ch in C.WSCN_CHANNELS:
        ch, min_score = ch if isinstance(ch, (tuple, list)) else (ch, C.WSCN_MIN_SCORE)
        try:
            data = get("https://api-one-wscn.awtmt.com/apiv1/content/lives",
                       params={"channel": ch, "limit": 30}).json()
            rows = data["data"]["items"]
        except Exception as e:  # noqa: BLE001
            print(f"[news] 华尔街见闻 {ch} 获取失败: {e}")
            continue
        items = [(f"wscn:{r['id']}", r) for r in rows]
        for _, r in pick_new(state, f"wscn:{ch}", items):
            if (r.get("score") or 1) < min_score:
                continue
            text = (r.get("content_text") or strip_html(r.get("content"))).strip()
            title = (r.get("title") or "").strip()
            if not text or not keyword_ok(title + text):
                continue
            important = (r.get("score") or 1) >= 2
            ts = datetime.fromtimestamp(r["display_time"], timezone.utc).isoformat()
            imgs = r.get("images") or []
            post(WEBHOOK, embeds=[embed(
                title=("🔴 " if important else "") + title if title else
                ("🔴 重要快讯" if important else None),
                description=clip(text, 3800),
                color=0xE53935 if important else 0x546E7A,
                footer="来源：华尔街见闻 7x24",
                timestamp=ts,
                image=imgs[0].get("uri") if imgs and isinstance(imgs[0], dict) else None,
            )])


def run_rss(state):
    for name, url in C.NEWS_RSS:
        try:
            feed = feedparser.parse(get(url).content)
        except Exception as e:  # noqa: BLE001
            print(f"[news] {name} 获取失败: {e}")
            continue
        items = [(f"rss:{e.get('id') or e.get('link')}", e) for e in feed.entries[:30]]
        for _, e in pick_new(state, f"rss:{name}", items):
            summary = strip_html(e.get("summary", ""))
            if not keyword_ok(e.get("title", "") + summary):
                continue
            post(WEBHOOK, embeds=[embed(
                title=e.get("title"), url=e.get("link"),
                description=clip(summary, 600), color=0xFFA726,
                footer=f"来源：{name}",
            )])


def main():
    state = load_state()
    try:
        run_wscn(state)
        run_rss(state)
    finally:
        save_state(state)


if __name__ == "__main__":
    main()
