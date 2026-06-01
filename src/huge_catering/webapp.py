from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from flask import Flask, Response, abort, redirect, render_template, request, send_from_directory, url_for

from .config import Settings, load_settings
from .draft_images import article_from_metadata, manual_images_from_metadata, render_metadata_article, save_manual_image, slot_options, valid_slot_ids
from .image_checks import ensure_article_images
from .pipeline import build_daily_article
from .image_prompt_workbench import build_workbench_from_metadata
from .render import render_article_html
from .tool_settings import ToolSettings, load_tool_settings, replace_setting, save_tool_settings, tool_settings_path
from .trends import load_or_fetch_trends
from .wechat import WeChatClient


BATCH_SIZE = 10


@dataclass(frozen=True)
class PreviewItem:
    publish_date: str
    title: str
    issue_number: int | None
    topic_name: str
    keywords: list[str]
    draft_media_id: str | None
    output_dir: Path
    archived: bool = False
    focus_keyword: str | None = None
    focus_count: int | None = None
    manual_images: dict[str, str] | None = None
    image_workbench: dict[str, Any] | None = None


def create_app() -> Flask:
    app = Flask(__name__)
    settings = load_settings()

    @app.get("/")
    def index() -> str:
        batch_dates = _read_current_batch(settings)
        items = [_preview_item(settings, item) for item in batch_dates]
        items = [item for item in items if item is not None]
        tool_settings = load_tool_settings(tool_settings_path(settings.output_dir))
        return render_template(
            "dashboard.html",
            items=items,
            today=date.today().isoformat(),
            has_wechat=settings.has_wechat_credentials,
            batch_size=BATCH_SIZE,
            tool_settings=tool_settings,
            archive_view=False,
            settings_saved=request.args.get("settings_saved") == "1",
            image_slots=slot_options(),
        )

    @app.get("/archive")
    def archive() -> str:
        items = [_preview_item(settings, item, archived=True) for item in _read_archived_dates(settings)]
        items = [item for item in items if item is not None]
        tool_settings = load_tool_settings(tool_settings_path(settings.output_dir))
        return render_template(
            "dashboard.html",
            items=items,
            today=date.today().isoformat(),
            has_wechat=settings.has_wechat_credentials,
            batch_size=BATCH_SIZE,
            tool_settings=tool_settings,
            archive_view=True,
            settings_saved=False,
            image_slots=slot_options(),
        )

    @app.get("/settings")
    def settings_page() -> Response:
        return redirect(url_for("index"))

    @app.post("/settings")
    def save_settings() -> str:
        path = tool_settings_path(settings.output_dir)
        existing = load_tool_settings(path)
        api_key = str(request.form.get("openai_api_key") or "").strip()
        if not api_key or api_key == "已保存，不在页面显示":
            api_key = existing.openai_api_key
        next_settings = ToolSettings(
            article_angle=str(request.form.get("article_angle") or "").strip(),
            keyword_override=str(request.form.get("keyword_override") or "").strip(),
            title_style=str(request.form.get("title_style") or "hot_warning").strip(),
            image_provider=str(request.form.get("image_provider") or "local").strip(),
            openai_api_key=api_key,
            openai_image_model=str(request.form.get("openai_image_model") or "gpt-image-1").strip(),
            openai_image_size=str(request.form.get("openai_image_size") or "1024x1024").strip(),
            openai_image_quality=str(request.form.get("openai_image_quality") or "low").strip(),
            huge_profile_prompt=str(request.form.get("huge_profile_prompt") or "").strip(),
            image_style_prompt=str(request.form.get("image_style_prompt") or "").strip(),
        )
        if next_settings.image_provider not in {"local", "openai"}:
            next_settings = replace_setting(next_settings, image_provider="local")
        save_tool_settings(path, next_settings)
        return redirect(url_for("index", settings_saved=1))

    @app.post("/generate")
    def generate_batch() -> Response:
        start_date = _parse_date(request.form.get("start_date")) or date.today()
        count = int(request.form.get("count") or BATCH_SIZE)
        tool_settings = load_tool_settings(tool_settings_path(settings.output_dir))
        trend_snapshot = None
        trend_keywords: list[str] = []
        if settings.enable_trend_content and not tool_settings.keyword_list:
            try:
                trend_snapshot = load_or_fetch_trends(output_dir=settings.output_dir, publish_date=start_date)
                trend_keywords = trend_snapshot.keywords[:count]
            except Exception:
                trend_snapshot = None
                trend_keywords = []
        dates: list[str] = []
        for offset in range(count):
            publish_date = start_date + timedelta(days=offset)
            keyword = trend_keywords[offset] if offset < len(trend_keywords) else None
            build_daily_article(
                settings,
                publish_date=publish_date,
                upload_draft=False,
                trend_snapshot=trend_snapshot,
                trend_keyword=keyword,
            )
            dates.append(publish_date.isoformat())
        _write_current_batch(settings, dates)
        return redirect(url_for("index"))

    @app.post("/upload")
    def upload_batch() -> Response:
        dates = request.form.getlist("dates") or _read_current_batch(settings)
        for value in dates:
            publish_date = _parse_date(value)
            if publish_date is None:
                continue
            metadata = _read_metadata(settings, publish_date)
            if metadata and metadata.get("draft_media_id"):
                continue
            if metadata:
                _upload_existing_draft(settings, publish_date)
            else:
                build_daily_article(settings, publish_date=publish_date, upload_draft=True)
        _write_current_batch(settings, [value for value in dates if _parse_date(value)])
        return redirect(url_for("index"))

    @app.post("/upload/<publish_date>")
    def upload_one(publish_date: str) -> Response:
        parsed = _parse_date(publish_date)
        if parsed is None:
            abort(404)
        metadata = _read_metadata(settings, parsed)
        if not metadata or not metadata.get("draft_media_id"):
            if metadata:
                _upload_existing_draft(settings, parsed)
            else:
                build_daily_article(settings, publish_date=parsed, upload_draft=True)
        return redirect(url_for("preview", publish_date=publish_date))

    @app.post("/preview/<publish_date>/images")
    def upload_preview_image(publish_date: str) -> Response:
        parsed = _parse_date(publish_date)
        if parsed is None:
            abort(404)
        slot_id = str(request.form.get("slot_id") or "")
        if slot_id not in valid_slot_ids():
            abort(400)
        image = request.files.get("image")
        if image is None or not image.filename:
            return redirect(url_for("preview", publish_date=publish_date))
        metadata = _read_metadata(settings, parsed)
        if not metadata:
            abort(404)
        run_dir = _draft_dir(settings, parsed)
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(image.filename).suffix or ".jpg") as tmp:
            tmp_path = Path(tmp.name)
        image.save(tmp_path)
        try:
            relative_path = save_manual_image(run_dir, slot_id, tmp_path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
        manual_images = manual_images_from_metadata(metadata)
        manual_images[slot_id] = relative_path
        metadata["manual_images"] = manual_images
        metadata["draft_media_id"] = None
        html = render_metadata_article(metadata, brand_name=settings.brand_name, run_dir=run_dir)
        image_check = ensure_article_images(html, html_path=run_dir / "article.html")
        metadata["image_check"] = {
            "ok": image_check.ok,
            "local_images": image_check.local_images,
            "remote_images": image_check.remote_images,
            "errors": image_check.errors,
            "copyright_policy": "文章正文只允许本地原创生成图片，上传后只允许微信素材域名图片。",
        }
        _write_metadata(settings, parsed, metadata)
        if request.form.get("return_to") == "index":
            return redirect(url_for("index"))
        return redirect(url_for("preview", publish_date=publish_date))

    @app.post("/preview/<publish_date>/images/remove")
    def remove_preview_image(publish_date: str) -> Response:
        parsed = _parse_date(publish_date)
        if parsed is None:
            abort(404)
        slot_id = str(request.form.get("slot_id") or "")
        metadata = _read_metadata(settings, parsed)
        if not metadata or slot_id not in valid_slot_ids():
            abort(404)
        manual_images = manual_images_from_metadata(metadata)
        relative_path = manual_images.pop(slot_id, "")
        if relative_path:
            image_path = (_draft_dir(settings, parsed) / relative_path).resolve()
            if _draft_dir(settings, parsed).resolve() in image_path.parents and image_path.exists():
                image_path.unlink()
        metadata["manual_images"] = manual_images
        metadata["draft_media_id"] = None
        run_dir = _draft_dir(settings, parsed)
        html = render_metadata_article(metadata, brand_name=settings.brand_name, run_dir=run_dir)
        image_check = ensure_article_images(html, html_path=run_dir / "article.html")
        metadata["image_check"] = {
            "ok": image_check.ok,
            "local_images": image_check.local_images,
            "remote_images": image_check.remote_images,
            "errors": image_check.errors,
            "copyright_policy": "文章正文只允许本地原创生成图片，上传后只允许微信素材域名图片。",
        }
        _write_metadata(settings, parsed, metadata)
        if request.form.get("return_to") == "index":
            return redirect(url_for("index"))
        return redirect(url_for("preview", publish_date=publish_date))

    @app.post("/drafts/action")
    def drafts_action() -> Response:
        action = request.form.get("action") or ""
        dates = request.form.getlist("dates")
        if action in {"archive_all", "delete_all"}:
            dates = _read_current_batch(settings)
        if action in {"delete_archive_all"}:
            dates = _read_archived_dates(settings)

        parsed_dates = [parsed for value in dates if (parsed := _parse_date(value)) is not None]
        if action in {"archive_selected", "archive_all"}:
            for publish_date in parsed_dates:
                _archive_draft(settings, publish_date)
            _write_current_batch(settings, _remove_dates(_read_current_batch(settings), parsed_dates))
            return redirect(url_for("index"))

        if action in {"delete_selected", "delete_all"}:
            for publish_date in parsed_dates:
                _delete_draft(settings, publish_date, archived=False)
            _write_current_batch(settings, _remove_dates(_read_current_batch(settings), parsed_dates))
            return redirect(url_for("index"))

        if action in {"delete_archive_selected", "delete_archive_all"}:
            for publish_date in parsed_dates:
                _delete_draft(settings, publish_date, archived=True)
            return redirect(url_for("archive"))

        return redirect(url_for("archive" if request.form.get("archive_view") else "index"))

    @app.get("/preview/<publish_date>")
    def preview(publish_date: str) -> str:
        parsed = _parse_date(publish_date)
        if parsed is None:
            abort(404)
        archived = request.args.get("archived") == "1"
        metadata = _read_metadata(settings, parsed, archived=archived)
        if not metadata:
            abort(404)
        workbench = metadata.get("image_prompt_workbench")
        if not isinstance(workbench, dict):
            workbench = build_workbench_from_metadata(metadata, brand_name=settings.brand_name)
        return render_template(
            "preview.html",
            metadata=metadata,
            publish_date=publish_date,
            archived=archived,
            image_workbench=workbench,
            image_slots=slot_options(),
            manual_images=manual_images_from_metadata(metadata),
        )

    @app.get("/outputs/<path:filename>")
    def outputs(filename: str) -> Response:
        return send_from_directory(settings.output_dir, filename)

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "ok": True,
            "has_wechat_credentials": settings.has_wechat_credentials,
            "output_dir": str(settings.output_dir),
        }

    return app


def main(argv: list[str] | None = None) -> int:
    settings = load_settings()
    parser = argparse.ArgumentParser(description="Run 胡哥说餐饮 web dashboard.")
    parser.add_argument("--host", default=os.getenv("WEB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("WEB_PORT", "8765")))
    args = parser.parse_args(argv)
    create_app().run(host=args.host, port=args.port)
    return 0


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _batch_path(settings: Settings) -> Path:
    return settings.output_dir.parent / "data" / "current_batch.json"


def _read_current_batch(settings: Settings) -> list[str]:
    path = _batch_path(settings)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    dates = raw.get("dates", []) if isinstance(raw, dict) else []
    return [str(item) for item in dates]


def _write_current_batch(settings: Settings, dates: list[str]) -> None:
    path = _batch_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"dates": dates}, ensure_ascii=False, indent=2), encoding="utf-8")


def _archive_root(settings: Settings) -> Path:
    return settings.output_dir / "_archive"


def _draft_dir(settings: Settings, publish_date: date, *, archived: bool = False) -> Path:
    base = _archive_root(settings) if archived else settings.output_dir
    return base / publish_date.isoformat()


def _read_archived_dates(settings: Settings) -> list[str]:
    root = _archive_root(settings)
    if not root.exists():
        return []
    dates = [
        item.name
        for item in root.iterdir()
        if item.is_dir() and _parse_date(item.name) is not None and (item / "metadata.json").exists()
    ]
    return sorted(dates, reverse=True)


def _read_metadata(settings: Settings, publish_date: date, *, archived: bool = False) -> dict[str, Any] | None:
    path = _draft_dir(settings, publish_date, archived=archived) / "metadata.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _write_metadata(settings: Settings, publish_date: date, metadata: dict[str, Any]) -> None:
    path = _draft_dir(settings, publish_date) / "metadata.json"
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def _preview_item(settings: Settings, publish_date: str, *, archived: bool = False) -> PreviewItem | None:
    parsed = _parse_date(publish_date)
    if parsed is None:
        return None
    metadata = _read_metadata(settings, parsed, archived=archived)
    if not metadata:
        return None
    return PreviewItem(
        publish_date=publish_date,
        title=str(metadata.get("title", "")),
        issue_number=metadata.get("issue_number"),
        topic_name=str(metadata.get("topic_name", "")),
        keywords=[str(item) for item in metadata.get("trend_keywords", [])],
        draft_media_id=metadata.get("draft_media_id"),
        output_dir=_draft_dir(settings, parsed, archived=archived),
        archived=archived,
        focus_keyword=str(metadata.get("trend_focus_keyword") or "") or None,
        focus_count=_focus_count(metadata),
        manual_images=manual_images_from_metadata(metadata),
        image_workbench=_workbench_from_metadata(metadata, settings),
    )


def _workbench_from_metadata(metadata: dict[str, Any], settings: Settings) -> dict[str, Any]:
    workbench = metadata.get("image_prompt_workbench")
    if isinstance(workbench, dict):
        return workbench
    return build_workbench_from_metadata(metadata, brand_name=settings.brand_name)


def _focus_count(metadata: dict[str, Any]) -> int | None:
    keyword = str(metadata.get("trend_focus_keyword") or "")
    counts = metadata.get("trend_keyword_counts")
    if not keyword or not isinstance(counts, dict):
        return None
    value = counts.get(keyword)
    return value if isinstance(value, int) else None


def _archive_draft(settings: Settings, publish_date: date) -> None:
    source = _draft_dir(settings, publish_date, archived=False).resolve()
    archive_root = _archive_root(settings).resolve()
    target = (archive_root / publish_date.isoformat()).resolve()
    output_root = settings.output_dir.resolve()
    if output_root not in source.parents or archive_root not in target.parents:
        raise ValueError("Invalid draft path")
    if not source.exists():
        return
    archive_root.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(source), str(target))


def _delete_draft(settings: Settings, publish_date: date, *, archived: bool = False) -> None:
    target = _draft_dir(settings, publish_date, archived=archived).resolve()
    allowed_root = (_archive_root(settings) if archived else settings.output_dir).resolve()
    if allowed_root not in target.parents:
        raise ValueError("Invalid draft path")
    if target.exists():
        shutil.rmtree(target)


def _remove_dates(values: list[str], publish_dates: list[date]) -> list[str]:
    remove = {item.isoformat() for item in publish_dates}
    return [value for value in values if value not in remove]


def _upload_existing_draft(settings: Settings, publish_date: date) -> None:
    metadata = _read_metadata(settings, publish_date)
    if not metadata:
        build_daily_article(settings, publish_date=publish_date, upload_draft=True)
        return
    if not settings.has_wechat_credentials:
        raise ValueError("Missing WECHAT_APP_ID or WECHAT_APP_SECRET in .env")
    run_dir = _draft_dir(settings, publish_date)
    article = article_from_metadata(metadata)
    client = WeChatClient(
        app_id=settings.wechat_app_id or "",
        app_secret=settings.wechat_app_secret or "",
        token_cache_path=Path("token_cache.json"),
    )
    remote_images: dict[str, str] = {}
    for slot_id, relative_path in manual_images_from_metadata(metadata).items():
        image_path = run_dir / relative_path
        if image_path.exists():
            remote_images[slot_id] = client.upload_content_image(image_path)
    html = render_article_html(
        article,
        brand_name=settings.brand_name,
        inline_images=remote_images,
        output_path=run_dir / "article.html",
    )
    image_check = ensure_article_images(html, html_path=run_dir / "article.html")
    thumb_media_id = client.upload_cover_thumb(run_dir / "cover.jpg")
    draft_media_id = client.add_draft(
        title=article.title,
        author=article.author,
        digest=article.digest,
        content=html,
        thumb_media_id=thumb_media_id,
        content_source_url=article.source_url,
    )
    metadata["draft_media_id"] = draft_media_id
    metadata["image_check"] = {
        "ok": image_check.ok,
        "local_images": image_check.local_images,
        "remote_images": image_check.remote_images,
        "errors": image_check.errors,
        "copyright_policy": "文章正文只允许本地原创生成图片，上传后只允许微信素材域名图片。",
    }
    _write_metadata(settings, publish_date, metadata)


if __name__ == "__main__":
    raise SystemExit(main())
