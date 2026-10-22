"""🧪 稀有 & 特种气体行业新闻：gasworld、gasworld 美国站 GAWDA Media、GAWDA、CGA、SEMI，可选 Google 新闻关键词。
标题和摘要机器翻译成中文，同时保留英文原标题和原文链接（gasworld 会员文章点链接登录后阅读）。"""
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urljoin

import feedparser
from bs4 import BeautifulSoup

import config as C
from common import clip, embed, get, load_state, post, save_state, strip_html, translate
from jobs.news import pick_new

WEBHOOK = "WEBHOOK_GAS"


def _soup(url):
    return BeautifulSoup(get(url).text, "html.parser")


def _meta(url):
    """抓文章页的 og 信息：摘要、配图、发布时间。"""
    try:
        s = _soup(url)
    except Exception:  # noqa: BLE001
        return {}

    def m(*names):
        for n in names:
            t = s.find("meta", attrs={"property": n}) or s.find("meta", attrs={"name": n})
            if t and t.get("content"):
                return t["content"].strip()
        return None
    return {"summary": m("og:description", "description", "twitter:description"),
            "image": m("og:image", "twitter:image"),
            "time": m("article:published_time", "og:updated_time"),
            "title": m("og:title")}


# ---------------- 各来源 ----------------
def src_rss(url):
    feed = feedparser.parse(get(url).content)
    out = []
    for e in feed.entries[:20]:
        ts = None
        if e.get("published"):
            try:
                ts = parsedate_to_datetime(e["published"]).isoformat()
            except Exception:  # noqa: BLE001
                pass
        out.append({"id": e.get("id") or e.get("link"), "title": e.get("title", ""),
                    "url": e.get("link"), "summary": strip_html(e.get("summary", "")),
                    "time": ts, "need_meta": False})
    return out


def src_gasworld(url):
    s = _soup(url)
    seen, out = {}, []
    for a in s.find_all("a", href=re.compile(r"/story/.+\.article")):
        href = urljoin(url, a["href"])
        title = a.get_text(" ", strip=True)
        if href not in seen:
            seen[href] = {"id": href, "title": title, "url": href, "need_meta": True}
            out.append(seen[href])
        elif len(title) > len(seen[href]["title"]):
            seen[href]["title"] = title
    return out[:30]


def src_cga(url):
    s = _soup(url)
    out = []
    for box in s.select(".article-glance")[:15]:
        a = box.select_one("h2 a") or box.find("a")
        if not a:
            continue
        href = urljoin(url, a["href"])
        out.append({"id": href, "title": a.get_text(" ", strip=True), "url": href, "need_meta": True})
    return out


def src_semi(url):
    s = _soup(url)
    seen, out = set(), []
    for a in s.find_all("a", href=re.compile(r"/en/semi-press-release/")):
        href = urljoin(url, a["href"])
        title = a.get_text(" ", strip=True)
        if href in seen or len(title) < 15:
            continue
        seen.add(href)
        out.append({"id": href, "title": title, "url": href, "need_meta": True})
    return out[:15]


def src_google(query):
    url = ("https://news.google.com/rss/search?q=" + quote_plus(query + " when:2d")
           + "&hl=en-US&gl=US&ceid=US:en")
    items = src_rss(url)
    for it in items:  # Google 新闻标题末尾是 " - 媒体名"
        it["summary"] = ""
    return items


KINDS = {"rss": src_rss, "gasworld": src_gasworld, "cga": src_cga, "semi": src_semi, "google": src_google}


# ---------------- 推送 ----------------
def hot_tags(text):
    up = text.upper()
    return [g for g in C.GAS_HIGHLIGHT if re.search(r"(?<![A-Z0-9])" + re.escape(g.upper()) + r"(?![A-Z0-9])", up)]


def run(state):
    import os
    from common import DRY_RUN
    if not DRY_RUN and not os.getenv(WEBHOOK):
        return
    if time.time() - state.get("gas_last_check", 0) < C.GAS_CHECK_MINUTES * 60:
        return
    state["gas_last_check"] = time.time()

    for name, kind, arg in C.GAS_SOURCES:
        try:
            items = KINDS[kind](arg)
        except Exception as e:  # noqa: BLE001
            print(f"[gas] {name} 获取失败: {e}")
            continue
        pairs = [(f"gas:{it['id']}", it) for it in items if it.get("id") and it.get("title")]
        for _, it in pick_new(state, f"gas:{name}", pairs):
            if it.get("need_meta"):
                meta = _meta(it["url"])
                it.setdefault("summary", meta.get("summary"))
                it["summary"] = it.get("summary") or meta.get("summary")
                it["image"] = meta.get("image")
                it["time"] = meta.get("time")
                if meta.get("title") and len(meta["title"]) > len(it["title"]):
                    it["title"] = meta["title"]
            title = re.sub(r"\s*[|–-]\s*gasworld\s*$", "", it["title"], flags=re.I).strip()
            summary = clip(it.get("summary") or "", 400)
            if kind == "google" and C.GAS_GOOGLE_STRICT and not hot_tags(title):
                continue
            zh_title = translate(title) or title
            zh_sum = translate(summary) if summary else ""
            tags = hot_tags(title + " " + summary)
            desc = f"*{title}*"
            if zh_sum or summary:
                desc += "\n\n" + (zh_sum or summary)
            if tags:
                desc += "\n\n🔥 涉及：" + "、".join(tags)
            ts = it.get("time")
            if ts:
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
                except ValueError:
                    ts = None
            post(WEBHOOK, embeds=[embed(
                title=clip(("🔥 " if tags else "") + zh_title, 250), url=it["url"],
                description=clip(desc, 3800),
                color=0xE11D48 if tags else 0x0EA5E9,
                thumbnail=it.get("image"), timestamp=ts,
                footer=f"来源：{name} · 标题和摘要为机器翻译",
            )])


def main():
    state = load_state()
    try:
        run(state)
    finally:
        save_state(state)


if __name__ == "__main__":
    main()
