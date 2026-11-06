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
    text = re.sub(r"\s*\(?@\w+\)?\s*$", "", text)    # 结尾的 @账号 / (@账号)
    text = re.sub(r"^\*+\s*", "", text)                 # Walter Bloomberg 的 * 开头
    text = re.sub(r"\s*\|?\s*(\$macro|\|?\s*FJ)\s*$", "", text, flags=re.I)  # FinancialJuice 结尾标签
    return text.strip()


CRYPTO_TICKERS = {"BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "AAVE", "USDT", "USDC", "PEPE", "SHIB"}


FAKE_TICKERS = {"MACRO", "FJ", "NEWS", "USD", "JPY", "EUR", "GBP", "CNH", "CNY", "SPX"}


def _has(words, up):
    for k in words:
        k = k.strip().upper()
        if not k:
            continue
        if k[0].isalnum():  # 英文整词匹配，兼容复数/所有格（STOCK → STOCKS、TESLA'S）
            if re.search(r"(?<![A-Z0-9])" + re.escape(k) + r"(?:S|ES|'S)?(?![A-Z0-9])", up):
                return True
        elif k in up:
            return True
    return False


def us_related(text):
    """只保留美股相关：
    ① 有美股代码或美国市场专属词（公司、美联储、标普…）→ 推
    ② 有外国市场词但没有①           → 不推（日本/韩国数据等）
    ③ 有通用市场词（股票、财报、通胀…）→ 推
    ④ 只有泛美国词（美国、特朗普、国会）→ 必须同时带经济词才推，纯政治新闻不推"""
    up = text.upper()
    if _has(C.TELEGRAM_EXCLUDE, up):
        return False
    tickers = set(re.findall(r"\$([A-Z]{1,5})\b", text)) - CRYPTO_TICKERS - FAKE_TICKERS
    if tickers or _has(C.NEWS_US_ANCHORS, up):
        return True
    if _has(C.NEWS_FOREIGN_WORDS, up):
        # 例外：美国 + 关税/贸易协定（如"美加接近达成关税协议"）仍然推
        return _has(C.NEWS_US_WEAK, up) and _has(["TARIFF", "TRADE DEAL", "TRADE AGREEMENT", "TRADE WAR"], up)
    if _has(C.NEWS_MARKET_WORDS, up):
        return True
    return _has(C.NEWS_US_WEAK, up) and _has(C.NEWS_ECON_WORDS, up)


_STOP = set("the a an and or of to in on for with by at from as is are was were be been has have had it its this that "
            "says said after over into amid just new will would could than more most about report reports per".split())


def _tokens(text):
    return {w for w in re.findall(r"[a-z0-9$]{3,}", text.lower()) if w not in _STOP}


def _bigrams(text):
    s = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def is_duplicate_zh(state, text):
    """中文快讯去重（华尔街见闻 / 富途常报同一条）：3 小时内两字词重合度高的只推一次。"""
    import time
    now = time.time()
    grams = _bigrams(text)
    recent = [r for r in state.get("news_recent_zh", []) if now - r[0] < C.NEWS_DEDUP_HOURS * 3600]
    dup = False
    if len(grams) >= 8:
        for _, prev in recent:
            p = set(prev.split("|"))
            if p and len(grams & p) / min(len(grams), len(p)) >= C.NEWS_DEDUP_SIMILARITY_ZH:
                dup = True
                break
    if not dup:
        recent.append([now, "|".join(sorted(grams))])
    state["news_recent_zh"] = recent[-150:]
    return dup


def is_duplicate(state, text):
    """不同来源转发的同一条新闻只推一次（英文原文词语重合度判断）。"""
    import time
    now = time.time()
    toks = _tokens(text)
    recent = [r for r in state.get("news_recent", []) if now - r[0] < C.NEWS_DEDUP_HOURS * 3600]
    dup = False
    if len(toks) >= 4:
        for _, prev in recent:
            p = set(prev.split())
            if p and len(toks & p) / len(toks | p) >= C.NEWS_DEDUP_SIMILARITY:
                dup = True
                break
    if not dup:
        recent.append([now, " ".join(sorted(toks))])
    state["news_recent"] = recent[-200:]
    return dup


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
        hook = (entry[2] if len(entry) > 2 else None) or WEBHOOK
        us_only = (entry[3] if len(entry) > 3 else False) or C.NEWS_US_ONLY
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
            policy = hook == WEBHOOK and re.search(C.WHITEHOUSE_POLICY_PATTERN, text.upper())
            if us_only and not us_related(text) and not policy:
                continue
            if text and is_duplicate(state, text):
                continue
            zh, ok = to_chinese(text) if text else ("", False)
            ts = None
            if it["time"]:
                try:
                    ts = datetime.fromisoformat(it["time"]).isoformat()
                except ValueError:
                    pass
            e = embed(description=zh[:3900] or "（图片）", color=0x2B2D31,
                      image=it["img"], timestamp=ts,
                      footer=f"来源：{label}" + (" · 机器翻译" if ok else ""))
            post(hook, embeds=[e])
            if policy:  # 议员炒股相关的政策新闻，同时转发到白宫内幕
                post("WEBHOOK_WHITEHOUSE", embeds=[e])


def main():
    from common import load_state, save_state
    state = load_state()
    try:
        run_telegram(state)
    finally:
        save_state(state)


if __name__ == "__main__":
    main()
