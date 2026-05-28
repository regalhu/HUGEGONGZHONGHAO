from __future__ import annotations

from pathlib import Path
import re
import textwrap

from PIL import Image, ImageDraw, ImageFont

from .models import Article


CANVAS_SIZE = (900, 383)
BG = "#f7f1e8"
INK = "#1f2933"
RED = "#b42318"
GOLD = "#c78b2f"
MUTED = "#5b6472"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: str,
    width: int,
    line_gap: int,
) -> int:
    lines: list[str] = []
    for paragraph in text.splitlines() or [text]:
        if re.search(r"[\u4e00-\u9fff]", paragraph):
            lines.extend([paragraph[index : index + width] for index in range(0, len(paragraph), width)])
        else:
            lines.extend(textwrap.wrap(paragraph, width=width, break_long_words=False))
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap if hasattr(font, "size") else 28
    return y


def create_cover(article: Article, brand_name: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", CANVAS_SIZE, BG)
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, 900, 383), fill=BG)
    draw.rectangle((0, 0, 28, 383), fill=RED)
    draw.rectangle((840, 0, 900, 383), fill=INK)
    draw.line((80, 72, 820, 72), fill=GOLD, width=4)
    draw.line((80, 312, 820, 312), fill=GOLD, width=4)

    draw.text((80, 38), brand_name, font=_font(28, bold=True), fill=RED)
    draw.text((80, 96), "餐饮要赚钱", font=_font(76, bold=True), fill=INK)
    draw.text((84, 180), "听我10句劝", font=_font(68, bold=True), fill=RED)
    draw.text(
        (86, 270),
        article.publish_date.strftime("%Y.%m.%d"),
        font=_font(28),
        fill=MUTED,
    )
    draw.text((640, 266), "老板每日复盘", font=_font(30, bold=True), fill=INK)

    image.save(output_path, quality=95)
    return output_path


def create_inline_card(article: Article, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (900, 620), "#fff7ed")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 900, 620), fill="#fff7ed")
    draw.rectangle((0, 0, 900, 22), fill=RED)
    draw.rectangle((46, 42, 854, 578), outline="#e3b15b", width=4)
    draw.rectangle((54, 50, 846, 570), outline="#ffffff", width=3)

    _draw_huge_cartoon(draw)

    keyword_text = " / ".join(article.trend_keywords[:3]) if article.trend_keywords else article.topic_name
    draw.text((330, 64), "胡哥漫画复盘", font=_font(42, bold=True), fill=INK)
    draw.text((332, 118), keyword_text[:28], font=_font(28, bold=True), fill=RED)

    summary = article.trend_summary or article.digest
    y = _draw_wrapped(draw, (330, 166), summary, _font(24), MUTED, 23, 8)
    y += 14

    draw.rounded_rectangle((330, y, 812, y + 54), radius=18, fill="#1f2933")
    draw.text((354, y + 11), "今天老板先抓这3件事", font=_font(26, bold=True), fill="#ffffff")
    y += 78

    for advice in article.advices[:3]:
        draw.ellipse((332, y + 2, 374, y + 44), fill=RED)
        draw.text((346, y + 5), str(advice.index), font=_font(25, bold=True), fill="#ffffff")
        draw.text((390, y + 4), advice.title, font=_font(28, bold=True), fill=INK)
        y += 55

    draw.text((330, 526), "胡哥说餐饮 | 把热点变成门店动作", font=_font(24), fill=MUTED)
    image.save(output_path, quality=95)
    return output_path


def _draw_huge_cartoon(draw: ImageDraw.ImageDraw) -> None:
    skin = "#f1c7a5"
    hair = "#2f241f"
    jacket = "#263238"
    shirt = "#ffffff"
    accent = RED

    draw.ellipse((92, 96, 266, 270), fill=skin, outline=INK, width=5)
    draw.pieslice((82, 72, 276, 204), 180, 360, fill=hair, outline=INK, width=4)
    draw.rectangle((118, 88, 246, 138), fill=hair)
    draw.ellipse((132, 164, 150, 182), fill=INK)
    draw.ellipse((206, 164, 224, 182), fill=INK)
    draw.arc((154, 186, 204, 224), 10, 170, fill=RED, width=4)
    draw.line((178, 176, 170, 198), fill="#9a6a55", width=3)
    draw.arc((122, 146, 158, 164), 200, 340, fill=INK, width=4)
    draw.arc((198, 146, 234, 164), 200, 340, fill=INK, width=4)

    draw.rounded_rectangle((82, 274, 280, 514), radius=34, fill=jacket, outline=INK, width=5)
    draw.polygon([(128, 280), (178, 410), (230, 280)], fill=shirt)
    draw.polygon([(176, 292), (202, 378), (176, 442), (150, 378)], fill=accent)
    draw.ellipse((54, 340, 116, 418), fill=skin, outline=INK, width=4)
    draw.line((104, 364, 160, 408), fill=skin, width=22)
    draw.line((104, 364, 160, 408), fill=INK, width=4)

    draw.rounded_rectangle((120, 442, 292, 532), radius=18, fill="#ffffff", outline=INK, width=4)
    draw.text((140, 458), "听我", font=_font(28, bold=True), fill=RED)
    draw.text((140, 492), "10句劝", font=_font(28, bold=True), fill=INK)
