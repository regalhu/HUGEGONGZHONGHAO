from __future__ import annotations

from pathlib import Path
import re
import textwrap
import hashlib

from PIL import Image, ImageDraw, ImageFont

from .models import Article
from .tool_settings import ToolSettings


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
    palette = _cover_palette(article)
    image = Image.new("RGB", CANVAS_SIZE, palette["bg"])
    draw = ImageDraw.Draw(image)

    draw.rectangle((0, 0, 900, 383), fill=palette["bg"])
    _draw_cover_pattern(draw, article, palette)

    keyword = article.trend_keywords[0] if article.trend_keywords else article.topic_name
    advice = article.advices[0].title if article.advices else "老板每日复盘"
    variant = article.issue_number % 3
    if variant == 0:
        draw.rectangle((0, 0, 34, 383), fill=palette["accent"])
        draw.rectangle((700, 0, 900, 383), fill=palette["dark"])
        draw.text((76, 34), brand_name, font=_font(27, bold=True), fill=palette["accent"])
        title_y = _draw_wrapped(draw, (76, 86), _cover_title(article.title), _font(46, bold=True), palette["ink"], 15, 8)
        draw.text((78, min(title_y + 16, 282)), f"关键词：{keyword}", font=_font(27, bold=True), fill=palette["accent"])
        draw.text((728, 80), "胡哥", font=_font(44, bold=True), fill="#ffffff")
        draw.text((728, 136), "说餐饮", font=_font(36, bold=True), fill="#ffffff")
        draw.text((728, 272), f"第{article.issue_number}篇", font=_font(27, bold=True), fill=palette["gold"])
    elif variant == 1:
        draw.rectangle((0, 0, 900, 58), fill=palette["dark"])
        draw.rectangle((64, 96, 836, 292), outline=palette["gold"], width=4)
        draw.text((70, 18), brand_name, font=_font(27, bold=True), fill="#ffffff")
        draw.text((710, 18), article.publish_date.strftime("%Y.%m.%d"), font=_font(24), fill=palette["gold"])
        title_y = _draw_wrapped(draw, (82, 112), _cover_title(article.title), _font(48, bold=True), palette["ink"], 16, 8)
        draw.text((84, min(title_y + 18, 302)), advice[:22], font=_font(27, bold=True), fill=palette["accent"])
        draw.text((650, 318), f"关键词 {keyword}", font=_font(25, bold=True), fill=palette["muted"])
    else:
        draw.rectangle((0, 0, 900, 383), outline=palette["dark"], width=18)
        draw.ellipse((54, 72, 218, 236), fill=palette["accent"])
        draw.text((86, 112), "10", font=_font(76, bold=True), fill="#ffffff")
        draw.text((94, 194), "句劝", font=_font(30, bold=True), fill="#ffffff")
        draw.text((266, 42), brand_name, font=_font(27, bold=True), fill=palette["accent"])
        title_y = _draw_wrapped(draw, (266, 92), _cover_title(article.title), _font(47, bold=True), palette["ink"], 15, 8)
        draw.text((268, min(title_y + 16, 286)), f"{keyword} / {advice[:16]}", font=_font(26, bold=True), fill=palette["muted"])
        draw.text((720, 318), f"NO.{article.issue_number}", font=_font(28, bold=True), fill=palette["accent"])

    image.save(output_path, quality=95)
    return output_path


def create_inline_card(article: Article, output_path: Path, tool_settings: ToolSettings | None = None) -> Path:
    if tool_settings and tool_settings.uses_openai_image:
        try:
            from .openai_images import generate_openai_inline_image

            return generate_openai_inline_image(article, tool_settings, output_path)
        except Exception:
            pass

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (900, 620), "#fff7ed")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 900, 620), fill="#fff7ed")
    draw.rectangle((0, 0, 900, 22), fill=RED)
    draw.rectangle((46, 42, 854, 578), outline="#e3b15b", width=4)
    draw.rectangle((54, 50, 846, 570), outline="#ffffff", width=3)

    _draw_huge_cartoon(draw)

    keyword_text = " / ".join(article.trend_keywords[:3]) if article.trend_keywords else article.topic_name
    scene = _scene_label(article)
    draw.text((330, 64), f"胡哥复盘：{scene}", font=_font(36, bold=True), fill=INK)
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


def _cover_title(title: str) -> str:
    return re.sub(r"｜\d+$", "", title)


def _cover_palette(article: Article) -> dict[str, str]:
    palettes = [
        {"bg": "#fff7ed", "ink": "#1f2933", "accent": "#b42318", "dark": "#20252d", "gold": "#c78b2f", "muted": "#5b6472"},
        {"bg": "#f3f7f0", "ink": "#1f2933", "accent": "#2f6f4e", "dark": "#17352a", "gold": "#b8872f", "muted": "#51635b"},
        {"bg": "#f7f4fb", "ink": "#252133", "accent": "#6d3f8f", "dark": "#2b2338", "gold": "#c4933a", "muted": "#625b6b"},
        {"bg": "#f3f7fb", "ink": "#1f2933", "accent": "#245c7a", "dark": "#183142", "gold": "#c78b2f", "muted": "#536575"},
    ]
    return palettes[article.issue_number % len(palettes)]


def _draw_cover_pattern(draw: ImageDraw.ImageDraw, article: Article, palette: dict[str, str]) -> None:
    seed = int(hashlib.sha1(article.title.encode("utf-8")).hexdigest()[:6], 16)
    for index in range(8):
        x = 40 + ((seed >> (index * 2)) % 760)
        y = 70 + ((seed >> (index + 8)) % 230)
        size = 18 + (seed >> index) % 34
        draw.rectangle((x, y, x + size, y + size), outline=palette["gold"], width=2)


def _scene_label(article: Article) -> str:
    text = " ".join(article.trend_keywords + [article.title, article.digest, article.trend_summary])
    scene_map = [
        ("外卖", "外卖订单"),
        ("食品安全", "后厨检查"),
        ("安全", "后厨检查"),
        ("成本", "成本账本"),
        ("复购", "顾客回头"),
        ("茶饮", "茶饮菜单"),
        ("预制菜", "菜品标准"),
        ("加盟", "门店管理"),
        ("客单价", "套餐设计"),
        ("投诉", "服务复盘"),
    ]
    for keyword, scene in scene_map:
        if keyword in text:
            return scene
    return "门店经营"


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
