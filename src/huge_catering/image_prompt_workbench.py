from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .models import Article


IMAGE_PROVIDER = "manual_chatgpt"


@dataclass(frozen=True)
class ImagePromptGroup:
    imageProvider: str
    purpose: str
    aspect_ratio: str
    chinese_prompt: str
    english_prompt: str
    style_notes: str
    negative_prompt: str

    @property
    def copy_text(self) -> str:
        return (
            f"图片用途：{self.purpose}\n"
            f"推荐尺寸比例：{self.aspect_ratio}\n\n"
            f"中文提示词：\n{self.chinese_prompt}\n\n"
            f"English prompt:\n{self.english_prompt}\n\n"
            f"风格说明：\n{self.style_notes}\n\n"
            f"禁止元素：\n{self.negative_prompt}"
        )


def build_workbench_from_article(article: Article, *, brand_name: str) -> dict[str, Any]:
    context = {
        "title": article.title,
        "topic": article.topic_name,
        "keywords": "、".join(article.trend_keywords[:5]) or article.topic_name,
        "summary": article.trend_summary or article.digest,
        "advices": "；".join(advice.title for advice in article.advices[:3]),
        "brand_name": brand_name,
    }
    return _build_workbench(context)


def build_workbench_from_metadata(metadata: dict[str, Any], *, brand_name: str) -> dict[str, Any]:
    advices = metadata.get("advices", [])
    advice_titles = []
    if isinstance(advices, list):
        for item in advices[:3]:
            if isinstance(item, dict):
                advice_titles.append(str(item.get("title", "")))
    context = {
        "title": str(metadata.get("title", "")),
        "topic": str(metadata.get("topic_name", "")),
        "keywords": "、".join(str(item) for item in metadata.get("trend_keywords", [])[:5]),
        "summary": str(metadata.get("trend_summary") or metadata.get("digest", "")),
        "advices": "；".join(item for item in advice_titles if item),
        "brand_name": brand_name,
    }
    return _build_workbench(context)


def _build_workbench(context: dict[str, str]) -> dict[str, Any]:
    groups = [
        _group(
            purpose="公众号封面图",
            aspect_ratio="2.35:1",
            scene="横版公众号头图，餐饮老板正在看经营数据，画面有门店、菜单、外卖订单和醒目的经营主题",
            english_scene="A wide WeChat article cover showing a restaurant owner reviewing business data, with a storefront, menu, delivery orders, and a clear business theme",
            context=context,
        ),
        _group(
            purpose="公众号文中配图 1",
            aspect_ratio="16:9",
            scene="文章中段解释图，胡哥形象在门店里复盘热点，旁边有成本、客流、复购和风险控制的视觉元素",
            english_scene="A 16:9 editorial illustration where Huge reviews the trend inside a restaurant, with visual elements for cost, traffic, repeat purchase, and risk control",
            context=context,
        ),
        _group(
            purpose="公众号文中配图 2",
            aspect_ratio="16:9",
            scene="行动清单式插画，餐饮团队围绕菜单、后厨标准、前厅话术和数据看板做当天改善",
            english_scene="A 16:9 action checklist illustration: a restaurant team improves menu design, kitchen standards, service scripts, and a data dashboard",
            context=context,
        ),
        _group(
            purpose="小红书封面图",
            aspect_ratio="3:4",
            scene="竖版小红书封面，强视觉标题感，餐饮老板视角，突出热点关键词和门店赚钱动作",
            english_scene="A vertical Xiaohongshu cover with strong editorial composition from a restaurant owner perspective, highlighting the trend keyword and money-making store actions",
            context=context,
        ),
        _group(
            purpose="视频号/抖音封面图",
            aspect_ratio="9:16",
            scene="短视频竖版封面，胡哥站在餐饮门店前，画面有热点冲击感和经营复盘氛围",
            english_scene="A vertical short-video cover with Huge standing in front of a restaurant, showing a strong trend impact and business review mood",
            context=context,
        ),
    ]
    return {
        "imageProvider": IMAGE_PROVIDER,
        "mode": "低成本人工协作模式",
        "chatgptUrl": "https://chatgpt.com/",
        "groups": [asdict(group) | {"copy_text": group.copy_text} for group in groups],
    }


def _group(
    *,
    purpose: str,
    aspect_ratio: str,
    scene: str,
    english_scene: str,
    context: dict[str, str],
) -> ImagePromptGroup:
    title = context["title"]
    keywords = context["keywords"] or context["topic"]
    summary = context["summary"]
    advices = context["advices"]
    brand_name = context["brand_name"]
    style = (
        f"{brand_name}统一品牌风格：原创商业漫画插画，适合公众号和社交媒体，清晰、明亮、专业、有餐饮烟火气；"
        "人物为原创中年中国餐饮经营顾问形象，短发，深色夹克，亲和但有判断力；"
        "画面重点表达经营洞察，不依赖大段文字。"
    )
    negative = (
        "不要错别字，不要多余文字，不要密集小字，不要二维码，不要真实品牌商标，"
        "不要侵权角色或名人形象，不要变形人物，不要多手多指，不要低清晰度，"
        "不要夸张恐怖表情，不要使用受版权保护图片，不要平台界面截图。"
    )
    chinese = (
        f"请生成一张{purpose}，推荐比例{aspect_ratio}。"
        f"文章标题是《{title}》，核心关键词是{keywords}。"
        f"正文主题：{summary}。"
        f"需要表达的经营动作：{advices or '把餐饮热点拆成门店当天能执行的动作'}。"
        f"画面设定：{scene}。"
        "图片要原创，不要直接写完整标题，可以用极少量无错字中文短语增强氛围。"
    )
    english = (
        f"Create an original image for {purpose}, aspect ratio {aspect_ratio}. "
        f"The article title is '{title}'. Key restaurant business keywords: {keywords}. "
        f"Main theme: {summary}. Action points: {advices or 'turn restaurant trends into practical store actions'}. "
        f"Scene: {english_scene}. Use an original Chinese restaurant business consultant character, warm but professional. "
        "Avoid long text; if text appears, keep it minimal and error-free."
    )
    return ImagePromptGroup(
        imageProvider=IMAGE_PROVIDER,
        purpose=purpose,
        aspect_ratio=aspect_ratio,
        chinese_prompt=chinese,
        english_prompt=english,
        style_notes=style,
        negative_prompt=negative,
    )
