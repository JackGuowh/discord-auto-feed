"""把川普的 Truth Social 帖子画成一张截图样式的卡片（白底、头像、名字、正文、时间）。"""
import io
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation",
             "/usr/share/fonts/truetype/liberation2"]


def font(bold, size):
    names = (["LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf"] if bold
             else ["LiberationSans-Regular.ttf", "DejaVuSans.ttf"])
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


def wrap(draw, text, fnt, width):
    lines = []
    for para in text.split("\n"):
        if not para.strip():
            lines.append("")
            continue
        words, cur = para.split(), ""
        for w in words:
            t = (cur + " " + w).strip()
            if draw.textlength(t, font=fnt) <= width:
                cur = t
            else:
                if cur:
                    lines.append(cur)
                while draw.textlength(w, font=fnt) > width:  # 超长单词硬切
                    cut = max(1, int(len(w) * width / draw.textlength(w, font=fnt)))
                    lines.append(w[:cut])
                    w = w[cut:]
                cur = w
        lines.append(cur)
    return lines


def render(text, when="", width=900, max_lines=60):
    W, pad = width, 40
    body_f, name_f, small_f = font(False, 24), font(True, 26), font(False, 20)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    text = text.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "—": "-", "–": "-", "…": "..."}))
    text = text.encode("ascii", "ignore").decode() or text  # 去掉 emoji（字体画不出来）
    lines = wrap(tmp, text, body_f, W - 2 * pad)
    if len(lines) > max_lines:
        lines = lines[:max_lines - 1] + ["…"]
    lh = 34
    H = pad + 64 + 24 + len(lines) * lh + 30 + 30 + pad
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    # 头像（红底圆形 + 首字母）
    d.ellipse((pad, pad, pad + 64, pad + 64), fill=(178, 34, 52))
    d.text((pad + 32, pad + 32), "DJT", font=font(True, 22), fill="white", anchor="mm")
    d.text((pad + 80, pad + 6), "Donald J. Trump", font=name_f, fill=(20, 20, 20))
    nw = d.textlength("Donald J. Trump", font=name_f)
    d.ellipse((pad + 88 + nw, pad + 12, pad + 108 + nw, pad + 32), fill=(29, 155, 240))
    d.text((pad + 80, pad + 38), "@realDonaldTrump", font=small_f, fill=(110, 110, 110))
    y = pad + 64 + 24
    for ln in lines:
        d.text((pad, y), ln, font=body_f, fill=(20, 20, 20))
        y += lh
    y += 16
    d.line((pad, y, W - pad, y), fill=(230, 230, 230), width=2)
    d.text((pad, y + 12), f"Truth Social{' · ' + when if when else ''}", font=small_f, fill=(110, 110, 110))
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
