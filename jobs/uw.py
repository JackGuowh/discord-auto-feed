"""⚡ 突发新闻：Unusual Whales（unusualwhales.com/news，和它推特 "Read more" 链接是同一批新闻）。"""
import json
import re

import config as C
from common import embed, get, load_state, post, save_state, translate
from jobs.news import pick_new
from jobs.telegram import us_related

WEBHOOK = "WEBHOOK_NEWS"


def fetch():
    html = get("https://unusualwhales.com/news").text
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError("页面里没有找到新闻数据（可能被 Cloudflare 拦截）")
    arts = json.loads(m.group(1))["props"]["pageProps"].get("featuredArticles") or []
    return sorted(arts, key=lambda a: a.get("created_at", ""), reverse=True)


def run(state):
    if not C.UNUSUAL_WHALES:
        return
    try:
        arts = fetch()
    except Exception as e:  # noqa: BLE001
        print(f"[uw] 获取失败: {e}")
        return
    pairs = [(f"uw:{a['slug']}", a) for a in arts if a.get("slug")]
    for _, a in pick_new(state, "unusualwhales", pairs):
        title = a.get("title", "").strip()
        import re
        policy = re.search(C.WHITEHOUSE_POLICY_PATTERN, title.upper())
        if not title or (C.NEWS_US_ONLY and not policy
                         and not us_related(title + " " + " ".join(a.get("tags") or []))):
            continue
        zh = translate(title)
        e = embed(description="快讯：" + (zh or title),
                  url=f"https://unusualwhales.com/news/{a['slug']}",
                  color=0x2B2D31, timestamp=a.get("created_at"),
                  footer="来源：Unusual Whales" + (" · 机器翻译" if zh else ""))
        post(WEBHOOK, embeds=[e])
        if policy:  # 议员炒股相关的政策新闻，同时转发到白宫内幕
            post("WEBHOOK_WHITEHOUSE", embeds=[e])


def main():
    state = load_state()
    try:
        run(state)
    finally:
        save_state(state)


if __name__ == "__main__":
    main()
