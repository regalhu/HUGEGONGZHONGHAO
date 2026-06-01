from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from PIL import Image

from .models import Advice, Article
from .render import render_article_html


@dataclass(frozen=True)
class ImageSlot:
    id: str
    label: str
    description: str


IMAGE_SLOTS = [
    ImageSlot("after_intro", "开头后", "适合放公众号文中配图 1 或文章主题图"),
    ImageSlot("after_advice_3", "第3句劝后", "适合放经营动作或案例说明图"),
    ImageSlot("after_advice_7", "第7句劝后", "适合放数据、复盘、避坑提醒图"),
    ImageSlot("before_conclusion", "结尾前", "适合放总结图或转发到社交平台的主视觉"),
]


def slot_options() -> list[dict[str, str]]:
    return [asdict(slot) for slot in IMAGE_SLOTS]


def valid_slot_ids() -> set[str]:
    return {slot.id for slot in IMAGE_SLOTS}


def article_from_metadata(metadata: dict[str, Any]) -> Article:
    advices = [
        Advice(
            index=int(item.get("index", index)),
            title=str(item.get("title", "")),
            body=str(item.get("body", "")),
        )
        for index, item in enumerate(metadata.get("advices", []), start=1)
        if isinstance(item, dict)
    ]
    return Article(
        title=str(metadata.get("title", "")),
        digest=str(metadata.get("digest", "")),
        author=str(metadata.get("author", "")),
        publish_date=date.fromisoformat(str(metadata.get("publish_date"))),
        topic_id=str(metadata.get("topic_id", "")),
        topic_name=str(metadata.get("topic_name", "")),
        issue_number=int(metadata.get("issue_number", 0)),
        intro=str(metadata.get("intro", "")),
        advices=advices,
        conclusion=str(metadata.get("conclusion", "")),
        trend_keywords=[str(item) for item in metadata.get("trend_keywords", [])],
        trend_summary=str(metadata.get("trend_summary", "")),
        trend_sources=[str(item) for item in metadata.get("trend_sources", [])],
        source_url=str(metadata.get("source_url", "")),
        tags=[str(item) for item in metadata.get("tags", [])],
    )


def manual_images_from_metadata(metadata: dict[str, Any]) -> dict[str, str]:
    raw = metadata.get("manual_images", {})
    if not isinstance(raw, dict):
        return {}
    return {key: str(value) for key, value in raw.items() if key in valid_slot_ids() and value}


def save_manual_image(run_dir: Path, slot_id: str, source_path: Path) -> str:
    if slot_id not in valid_slot_ids():
        raise ValueError(f"Unknown image slot: {slot_id}")
    target_dir = run_dir / "manual-images"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{slot_id}.jpg"
    image = Image.open(source_path).convert("RGB")
    image.save(target, format="JPEG", quality=92)
    return f"manual-images/{slot_id}.jpg"


def save_cover_image(run_dir: Path, source_path: Path) -> Path:
    target = run_dir / "cover.jpg"
    image = Image.open(source_path).convert("RGB")
    image.save(target, format="JPEG", quality=94)
    return target


def render_metadata_article(metadata: dict[str, Any], *, brand_name: str, run_dir: Path) -> str:
    article = article_from_metadata(metadata)
    return render_article_html(
        article,
        brand_name=brand_name,
        inline_images={},
        output_path=run_dir / "article.html",
    )
