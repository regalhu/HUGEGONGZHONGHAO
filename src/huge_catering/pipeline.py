from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
from pathlib import Path

from .config import Settings
from .content import choose_topic, generate_article, topic_from_trends, topics_from_raw
from .history import history_path, issue_number_for_date, read_history, record_history
from .image_checks import ensure_article_images, validate_article_images
from .image_prompt_workbench import build_workbench_from_article
from .images import create_cover
from .render import render_article_html
from .topic_factory import ensure_fresh_topic_batch
from .tool_settings import load_tool_settings, tool_settings_path
from .trends import TrendSnapshot, load_or_fetch_trends, snapshot_for_keyword
from .wechat import WeChatClient


@dataclass(frozen=True)
class PipelineResult:
    output_dir: Path
    article_html: Path
    cover_image: Path
    inline_image: Path | None
    metadata_json: Path
    draft_media_id: str | None = None


def build_daily_article(
    settings: Settings,
    *,
    publish_date: date,
    upload_draft: bool = False,
    seed: int | None = None,
    trend_snapshot: TrendSnapshot | None = None,
    trend_keyword: str | None = None,
    issue_number_override: int | None = None,
) -> PipelineResult:
    run_dir = settings.output_dir / publish_date.strftime("%Y-%m-%d")
    tool_settings = load_tool_settings(tool_settings_path(settings.output_dir))
    history_file = history_path(settings.output_dir)
    history = read_history(history_file)
    used_trend_snapshot = trend_snapshot
    issue_number = issue_number_override or issue_number_for_date(
        history,
        publish_date,
        start_issue_number=settings.start_issue_number,
    )
    selected_trend_keyword: str | None = None
    if settings.enable_trend_content:
        try:
            snapshot = trend_snapshot or load_or_fetch_trends(output_dir=settings.output_dir, publish_date=publish_date)
            used_trend_snapshot = snapshot
            selected_trend_keyword = _non_consecutive_trend_keyword(
                settings=settings,
                publish_date=publish_date,
                snapshot=snapshot,
                requested_keyword=trend_keyword,
            )
            if selected_trend_keyword:
                snapshot = snapshot_for_keyword(snapshot, selected_trend_keyword)
                used_trend_snapshot = snapshot
            topic = topic_from_trends(
                snapshot,
                article_type=tool_settings.article_type,
                title_variant=issue_number + (seed or 0),
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
        article_type=tool_settings.article_type,
    )

    cover_path = create_cover(article, settings.brand_name, run_dir / "cover.jpg")
    html_path = run_dir / "article.html"
    html = render_article_html(
        article,
        brand_name=settings.brand_name,
        inline_images={},
        output_path=html_path,
    )
    preview_image_check = ensure_article_images(html, html_path=html_path)

    draft_media_id: str | None = None
    upload_image_check = None
    if upload_draft:
        if not settings.has_wechat_credentials:
            raise ValueError("Missing WECHAT_APP_ID or WECHAT_APP_SECRET in .env")
        client = WeChatClient(
            app_id=settings.wechat_app_id or "",
            app_secret=settings.wechat_app_secret or "",
            token_cache_path=Path("token_cache.json"),
        )
        html = render_article_html(
            article,
            brand_name=settings.brand_name,
            inline_images={},
            output_path=html_path,
        )
        upload_image_check = ensure_article_images(html, html_path=html_path)
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
                "intro": article.intro,
                "conclusion": article.conclusion,
                "source_url": article.source_url,
                "trend_keywords": article.trend_keywords,
                "trend_summary": article.trend_summary,
                "trend_keyword_counts": (used_trend_snapshot.keyword_counts if used_trend_snapshot else None) or {},
                "trend_focus_keyword": selected_trend_keyword,
                "trend_sources": article.trend_sources or (used_trend_snapshot.source_titles if used_trend_snapshot else [])[:10],
                "cover_image": str(cover_path),
                "article_html": str(html_path),
                "draft_media_id": draft_media_id,
                "manual_images": {},
                "image_check": {
                    "ok": (upload_image_check or preview_image_check).ok,
                    "local_images": (upload_image_check or preview_image_check).local_images,
                    "remote_images": (upload_image_check or preview_image_check).remote_images,
                    "errors": (upload_image_check or preview_image_check).errors,
                    "copyright_policy": "文章正文只允许本地原创生成图片，上传后只允许微信素材域名图片。",
                },
                "image_prompt_workbench": build_workbench_from_article(article, brand_name=settings.brand_name),
                "tags": article.tags,
                "tool_settings": {
                    "article_type": tool_settings.article_type,
                    "next_issue_number": tool_settings.next_issue_number,
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
        inline_image=None,
        metadata_json=metadata_path,
        draft_media_id=draft_media_id,
    )


def _non_consecutive_trend_keyword(
    *,
    settings: Settings,
    publish_date: date,
    snapshot: TrendSnapshot,
    requested_keyword: str | None,
) -> str | None:
    previous_keyword = _previous_trend_keyword(settings, publish_date)
    candidates: list[str] = []
    if requested_keyword:
        candidates.append(requested_keyword)
    candidates.extend(snapshot.keywords)

    seen: set[str] = set()
    unique_candidates = []
    for keyword in candidates:
        clean = str(keyword).strip()
        if clean and clean not in seen:
            seen.add(clean)
            unique_candidates.append(clean)

    if not unique_candidates:
        return None
    for keyword in unique_candidates:
        if keyword != previous_keyword:
            return keyword
    return unique_candidates[0]


def _previous_trend_keyword(settings: Settings, publish_date: date) -> str | None:
    metadata_path = settings.output_dir / (publish_date - timedelta(days=1)).isoformat() / "metadata.json"
    if not metadata_path.exists():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    keyword = metadata.get("trend_focus_keyword")
    return str(keyword).strip() if keyword else None
