from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path

from .config import Settings
from .content import choose_topic, generate_article, topic_from_trends, topics_from_raw
from .history import history_path, issue_number_for_date, read_history, record_history
from .images import create_cover, create_inline_card
from .render import render_article_html
from .topic_factory import ensure_fresh_topic_batch
from .tool_settings import load_tool_settings, tool_settings_path
from .trends import load_or_fetch_trends
from .wechat import WeChatClient


@dataclass(frozen=True)
class PipelineResult:
    output_dir: Path
    article_html: Path
    cover_image: Path
    inline_image: Path
    metadata_json: Path
    draft_media_id: str | None = None


def build_daily_article(
    settings: Settings,
    *,
    publish_date: date,
    upload_draft: bool = False,
    seed: int | None = None,
) -> PipelineResult:
    run_dir = settings.output_dir / publish_date.strftime("%Y-%m-%d")
    tool_settings = load_tool_settings(tool_settings_path(settings.output_dir))
    history_file = history_path(settings.output_dir)
    history = read_history(history_file)
    issue_number = issue_number_for_date(
        history,
        publish_date,
        start_issue_number=settings.start_issue_number,
    )
    if settings.enable_trend_content:
        try:
            topic = topic_from_trends(
                load_or_fetch_trends(output_dir=settings.output_dir, publish_date=publish_date),
                title_style=tool_settings.title_style,
                article_angle=tool_settings.article_angle,
                keyword_override=tool_settings.keyword_list or None,
                title_variant=issue_number,
            )
        except Exception:
            raw_topics = ensure_fresh_topic_batch(
                settings.topic_library_path,
                history=history,
            )
            topic = choose_topic(
                topics_from_raw(raw_topics),
                publish_date=publish_date,
                history=history,
                seed=seed,
            )
    else:
        raw_topics = ensure_fresh_topic_batch(
            settings.topic_library_path,
            history=history,
        )
        topic = choose_topic(
            topics_from_raw(raw_topics),
            publish_date=publish_date,
            history=history,
            seed=seed,
        )
    article = generate_article(
        brand_name=settings.brand_name,
        author_name=settings.author_name,
        publish_date=publish_date,
        topic=topic,
        issue_number=issue_number,
    )

    cover_path = create_cover(article, settings.brand_name, run_dir / "cover.jpg")
    inline_path = create_inline_card(article, run_dir / "inline-card.jpg", tool_settings=tool_settings)
    html_path = run_dir / "article.html"
    html = render_article_html(
        article,
        brand_name=settings.brand_name,
        inline_image_url=None,
        output_path=html_path,
    )

    draft_media_id: str | None = None
    if upload_draft:
        if not settings.has_wechat_credentials:
            raise ValueError("Missing WECHAT_APP_ID or WECHAT_APP_SECRET in .env")
        client = WeChatClient(
            app_id=settings.wechat_app_id or "",
            app_secret=settings.wechat_app_secret or "",
            token_cache_path=Path("token_cache.json"),
        )
        inline_url = client.upload_content_image(inline_path)
        html = render_article_html(
            article,
            brand_name=settings.brand_name,
            inline_image_url=inline_url,
            output_path=html_path,
        )
        thumb_media_id = client.upload_cover_thumb(cover_path)
        draft_media_id = client.add_draft(
            title=article.title,
            author=article.author,
            digest=article.digest,
            content=html,
            thumb_media_id=thumb_media_id,
            content_source_url=article.source_url,
        )

    metadata_path = run_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "title": article.title,
                "digest": article.digest,
                "author": article.author,
                "publish_date": article.publish_date.isoformat(),
                "topic_id": article.topic_id,
                "topic_name": article.topic_name,
                "issue_number": article.issue_number,
                "trend_keywords": article.trend_keywords,
                "trend_summary": article.trend_summary,
                "cover_image": str(cover_path),
                "inline_image": str(inline_path),
                "article_html": str(html_path),
                "draft_media_id": draft_media_id,
                "tags": article.tags,
                "tool_settings": {
                    "article_angle": tool_settings.article_angle,
                    "title_style": tool_settings.title_style,
                    "image_provider": tool_settings.image_provider,
                    "openai_image_model": tool_settings.openai_image_model,
                    "openai_image_size": tool_settings.openai_image_size,
                    "openai_image_quality": tool_settings.openai_image_quality,
                },
                "advices": [
                    {"index": item.index, "title": item.title, "body": item.body}
                    for item in article.advices
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    record_history(
        history_file,
        publish_date=publish_date,
        topic_id=article.topic_id,
        title=article.title,
        issue_number=article.issue_number,
    )
    return PipelineResult(
        output_dir=run_dir,
        article_html=html_path,
        cover_image=cover_path,
        inline_image=inline_path,
        metadata_json=metadata_path,
        draft_media_id=draft_media_id,
    )
