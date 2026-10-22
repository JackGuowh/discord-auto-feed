"""公共工具：HTTP、Discord Webhook 推送、去重状态、免费翻译。"""
import html
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "state.json"
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": "*/*",
                        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8"})


def get(url, **kw):
    kw.setdefault("timeout", 20)
    r = session.get(url, **kw)
    r.raise_for_status()
    return r


# ---------------- 去重状态 ----------------
def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1),
                          encoding="utf-8")


def remember(state, key, ids, keep=500):
    """把新 id 记入 state[key]，只保留最近 keep 条。"""
    seen = state.get(key, [])
    seen = [i for i in seen if i not in ids] + list(ids)
    state[key] = seen[-keep:]


# ---------------- 文本处理 ----------------
def strip_html(s):
    s = re.sub(r"<br\s*/?>|</p>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def clip(s, n):
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


def translate(text, target="zh-CN"):
    """用 Google 翻译免费网页接口翻译，失败时返回 None（调用方回退到原文）。"""
    text = (text or "").strip()
    if not text:
        return ""
    out = []
    # 按段落切块，单块不超过 1500 字符（GET 请求长度限制）
    chunks, buf = [], ""
    for para in text.split("\n"):
        if len(buf) + len(para) > 1500 and buf:
            chunks.append(buf)
            buf = ""
        buf += para + "\n"
    if buf:
        chunks.append(buf)
    try:
        for c in chunks:
            r = get("https://translate.googleapis.com/translate_a/single",
                    params={"client": "gtx", "sl": "auto", "tl": target,
                            "dt": "t", "q": c})
            data = r.json()
            out.append("".join(seg[0] for seg in data[0] if seg and seg[0]))
            time.sleep(0.5)
        return "".join(out).strip()
    except Exception as e:  # noqa: BLE001
        print(f"[translate] 失败，回退原文: {e}")
        return None


def now_et():
    return datetime.now(timezone.utc).astimezone(ET)


# ---------------- Discord 推送 ----------------
def post(webhook_env, content=None, embeds=None, username=None, avatar_url=None):
    """往 Discord Webhook 发一条消息。webhook_env 是存放 Webhook 链接的环境变量名。"""
    payload = {"allowed_mentions": {"parse": []}}
    if content:
        payload["content"] = clip(content, 2000)
    if embeds:
        payload["embeds"] = embeds[:10]
    if username:
        payload["username"] = username
    if avatar_url:
        payload["avatar_url"] = avatar_url

    url = os.getenv(webhook_env, "").strip()
    if DRY_RUN or not url:
        if not DRY_RUN:
            print(f"[warn] 环境变量 {webhook_env} 未设置，改为只打印")
        print(f"----- [{webhook_env}] -----")
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return True

    for attempt in range(5):
        r = requests.post(url, json=payload, timeout=20)
        if r.status_code == 429:  # 频率限制：按 Discord 要求等待
            wait = float(r.json().get("retry_after", 2))
            time.sleep(wait + 0.5)
            continue
        if r.status_code >= 400:
            print(f"[post] {webhook_env} 失败 {r.status_code}: {r.text[:300]}")
            return False
        time.sleep(1.2)  # 同一 Webhook 每秒不要超过 1 条左右
        return True
    return False


def embed(title=None, description=None, url=None, color=0x5865F2,
          fields=None, footer=None, timestamp=None, image=None, thumbnail=None):
    e = {"color": color}
    if title:
        e["title"] = clip(title, 256)
    if description:
        e["description"] = clip(description, 4000)
    if url:
        e["url"] = url
    if fields:
        e["fields"] = [{"name": clip(f[0], 256), "value": clip(f[1], 1024) or "—",
                        "inline": f[2] if len(f) > 2 else False}
                       for f in fields[:25]]
    if footer:
        e["footer"] = {"text": clip(footer, 2048)}
    if timestamp:
        e["timestamp"] = timestamp
    if image:
        e["image"] = {"url": image}
    if thumbnail:
        e["thumbnail"] = {"url": thumbnail}
    return e
