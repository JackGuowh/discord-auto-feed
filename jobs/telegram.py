"""⚡ 突发新闻（X/推特新闻账号）：通过这些账号的 Telegram 公开镜像频道免费抓取，
机器翻译成中文后推送，格式类似「刚刚：……」「突发：……」。"""
import re
from datetime import datetime

from bs4 import BeautifulSoup

import config as C
from common import embed, get, post, translate
from jobs.news import pick_new

WEBHOOK = "WEBHOOK_NEWS"

# 英文开头 → 中文前缀
PREFIXES = [
    (r"^\W*(JUST IN|JUST_IN)\s*[:：-]\s*", "刚刚："),
    (r"^\W*(BREAKING)\s*[:：-]\s*", "突发："),
    (r"^\W*(URGENT)\s*[:：-]\s*", "紧急："),
    (r"^\W*(NEW|LATEST|UPDATE)\s*[:：-]\s*", "最新："),
    (r"^\W*(FLASH|ALERT)\s*[:：-]\s*", "快讯："),
]


def parse_channel(html):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for msg in soup.select(".tgme_widget_message[data-post]"):
        pid = msg["data-post"]
        tnode = msg.select_one(".tgme_widget_message_text")
        if tnode:
            for br in tnode.find_all("br"):
                br.replace_with("\n")
            text = tnode.get_text().strip()
        else:
            text = ""
        img = None
        ph = msg.select_one(".tgme_widget_message_photo_wrap")
        if ph and ph.get("style"):
            m = re.search(r"url\(['\"]?(.*?)['\"]?\)", ph["style"])
            img = m.group(1) if m else None
        t = msg.select_one("time[datetime]")
        out.append({"id": pid, "text": text, "img": img,
                    "time": t["datetime"] if t else None})
    out.reverse()  # 新 → 旧
    return out


def clean(text, channel):
    text = re.sub(r"\s*@" + re.escape(channel) + r"\s*$", "", text, flags=re.I)
    text = re.sub(r"\s*@\w+\s*$", "", text)          # 结尾的 @账号
    text = re.sub(r"^\*+\s*", "", text)                 # Walter Bloomberg 的 * 开头
    return text.strip()


CRYPTO_TICKERS = {"BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "AAVE", "USDT", "USDC", "PEPE", "SHIB"}


def us_related(text):
    """只保留美股相关：含美股代码（$TSLA）或美股/美国宏观关键词，且不含加密货币词。"""
    up = text.upper()
    if any(x.upper() in up for x in C.TELEGRAM_EXCLUDE):
        return False
    tickers = set(re.findall(r"\$([A-Z]{1,5})\b", text))
    if tickers - CRYPTO_TICKERS:
        return True
    return any(k.upper() in up for k in C.TELEGRAM_KEYWORDS)


def to_chinese(text):
    prefix = "快讯："
    for pat, zh in PREFIXES:
        if re.match(pat, text, flags=re.I):
            text = re.sub(pat, "", text, flags=re.I)
            prefix = zh
            break
    # 全大写的标题先转成句子大小写，翻译效果更好
    letters = [c for c in text if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.8:
        text = text.capitalize()
    zh = translate(text)
    return prefix + (zh if zh else text), bool(zh)


def run_telegram(state):
    for entry in C.TELEGRAM_CHANNELS:
        ch, label = entry[0], entry[1]
        hook = entry[2] if len(entry) > 2 else WEBHOOK
        try:
            items = parse_channel(get(f"https://t.me/s/{ch}").text)
        except Exception as e:  # noqa: BLE001
            print(f"[telegram] {ch} 获取失败: {e}")
            continue
        pairs = [(f"tg:{it['id']}", it) for it in items]
        for _, it in pick_new(state, f"tg:{ch}", pairs):
            text = clean(it["text"], ch)
            if not text and not it["img"]:
                continue
            if not us_related(text):
                continue
            zh, ok = to_chinese(text) if text else ("", False)
            ts = None
            if it["time"]:
                try:
                    ts = datetime.fromisoformat(it["time"]).isoformat()
                except ValueError:
                    pass
            post(hook, embeds=[embed(
                description=zh[:3900] or "（图片）", color=0x2B2D31,
                image=it["img"], timestamp=ts,
                footer=f"来源：{label}" + (" · 机器翻译" if ok else ""),
            )])


def main():
    from common import load_state, save_state
    state = load_state()
    try:
        run_telegram(state)
    finally:
        save_state(state)


if __name__ == "__main__":
    main()
