"""🇺🇸 川普 Truth Social 帖子（机器翻译）+ 🏛️ 白宫新闻稿。"""
import re
from email.utils import parsedate_to_datetime

import feedparser

import config as C
from common import (clip, embed, get, load_state, post, save_state,
                    strip_html, translate)
from jobs.news import pick_new

WEBHOOK_TRUMP = "WEBHOOK_TRUMP"
WEBHOOK_WH = "WEBHOOK_WHITEHOUSE"   # 没设置的话会推到 WEBHOOK_TRUMP


def iso(entry):
    try:
        return parsedate_to_datetime(entry.get("published")).isoformat()
    except Exception:  # noqa: BLE001
        return None


def run_trump(state):
    try:
        feed = feedparser.parse(get(C.TRUMP_FEED).content)
    except Exception as e:  # noqa: BLE001
        print(f"[trump] 获取失败: {e}")
        return
    items = [(f"truth:{e.get('id') or e.get('link')}", e) for e in feed.entries[:30]]
    for _, e in pick_new(state, "truth", items):
        ptype = e.get("archive_posttype", "original")
        if ptype == "repost" and not C.TRUMP_INCLUDE_REPOSTS:
            continue
        raw = e.get("summary", "")
        # 去掉 "View image / View video" 链接段落，单独处理媒体
        media = re.findall(r'href="([^"]+\.(?:jpg|jpeg|png|gif|mp4|mov))"', raw, re.I)
        raw = re.sub(r"<p><a [^>]*>View (?:image|video)</a></p>", "", raw)
        raw = re.sub(r"<blockquote>.*?</blockquote>", "", raw, flags=re.S)
        raw = re.sub(r"<p>(?:Reposted|Quoted) <a[^>]*>.*?</a></p>", "", raw)
        text = strip_html(raw)
        link = e.get("truth_originalurl") or e.get("link")

        images = [m for m in media if not m.lower().endswith((".mp4", ".mov"))]
        videos = [m for m in media if m.lower().endswith((".mp4", ".mov"))]

        if text:
            zh = translate(text)
            desc = zh if zh else text
            fields = [("原文", clip(text, 1000))] if zh else []
        else:
            desc = "（发布了" + ("视频" if videos else "图片") + "）"
            fields = []
        if videos:
            fields.append(("视频", videos[0]))
        label = {"repost": "转帖", "quote": "引用帖"}.get(ptype, "新帖")
        post(WEBHOOK_TRUMP, embeds=[embed(
            title=f"🇺🇸 川普 Truth Social {label}",
            url=link, description=clip(desc, 3800), fields=fields,
            color=0xC62828, footer="机器翻译仅供参考 · 来源：Truth Social",
            timestamp=iso(e), image=images[0] if images else None,
        )])


def run_whitehouse(state):
    import os
    hook = WEBHOOK_WH if os.getenv(WEBHOOK_WH) else WEBHOOK_TRUMP
    try:
        feed = feedparser.parse(get(C.WHITEHOUSE_FEED).content)
    except Exception as e:  # noqa: BLE001
        print(f"[whitehouse] 获取失败: {e}")
        return
    items = [(f"wh:{e.get('id') or e.get('link')}", e) for e in feed.entries[:20]]
    for _, e in pick_new(state, "whitehouse", items):
        title = e.get("title", "")
        summary = clip(strip_html(e.get("summary", "")), 500)
        zh_title = translate(title) or title
        zh_sum = translate(summary) if summary else ""
        cats = ", ".join(t.get("term", "") for t in e.get("tags", [])[:3])
        post(hook, embeds=[embed(
            title=f"🏛️ {zh_title}", url=e.get("link"),
            description=(zh_sum or summary) + f"\n\n*{title}*",
            color=0x1A237E, timestamp=iso(e),
            footer="白宫官网" + (f" · {cats}" if cats else "") + " · 机器翻译仅供参考",
        )])


def main():
    state = load_state()
    try:
        run_trump(state)
        run_whitehouse(state)
    finally:
        save_state(state)


if __name__ == "__main__":
    main()
