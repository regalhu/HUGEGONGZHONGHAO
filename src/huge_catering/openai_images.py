from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

from PIL import Image
import requests

from .models import Article
from .tool_settings import ToolSettings


OPENAI_IMAGE_ENDPOINT = "https://api.openai.com/v1/images/generations"


def generate_openai_inline_image(article: Article, settings: ToolSettings, output_path: Path) -> Path:
    prompt = _build_prompt(article, settings)
    payload = {
        "model": settings.openai_image_model or "gpt-image-1",
        "prompt": prompt,
        "size": settings.openai_image_size or "1024x1024",
        "quality": settings.openai_image_quality or "low",
        "n": 1,
    }
    response = requests.post(
        OPENAI_IMAGE_ENDPOINT,
        headers={
            "Authorization": f"Bearer {settings.openai_api_key.strip()}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=180,
    )
    response.raise_for_status()
    data = response.json()
    item = data.get("data", [{}])[0]
    image_bytes = _image_bytes(item)
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="JPEG", quality=92)
    return output_path


def _image_bytes(item: dict[str, object]) -> bytes:
    b64_json = item.get("b64_json")
    if isinstance(b64_json, str) and b64_json:
        return base64.b64decode(b64_json)

    url = item.get("url")
    if isinstance(url, str) and url:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        return response.content

    raise ValueError("OpenAI image response did not include b64_json or url")


def _build_prompt(article: Article, settings: ToolSettings) -> str:
    keywords = "、".join(article.trend_keywords[:5]) or article.topic_name
    top_advices = "；".join(advice.title for advice in article.advices[:3])
    return (
        "为微信公众号文章生成一张正文配图。"
        f"文章标题：{article.title}。"
        f"热点关键词：{keywords}。"
        f"文章主旨：{article.trend_summary or article.digest}。"
        f"画面总结：{top_advices}。"
        f"固定人物形象：{settings.huge_profile_prompt}。"
        f"风格要求：{settings.image_style_prompt}。"
        "画面中可以出现餐饮门店、菜单、外卖订单、后厨检查、经营数据看板等元素。"
        "必须是全新原创插画，不要引用影视、动漫、名人、真实品牌商标或受版权保护的图片。"
        "不要生成二维码、公众号界面截图、密集小字或真实品牌商标。"
    )
