from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any

from flask import Flask, Response, abort, jsonify, redirect, render_template, request, send_from_directory, url_for

from .config import Settings, load_settings
from .draft_images import article_from_metadata, manual_images_from_metadata, render_metadata_article, save_cover_image, save_manual_image, slot_options, valid_slot_ids
from .image_checks import ensure_article_images
from .pipeline import build_daily_article
from .image_prompt_workbench import build_workbench_from_metadata
from .quality import check_article_quality
from .reference_search import format_references_for_prompt, search_reference_articles
from .render import render_article_html
from .topic_planner import TopicPlan, topic_planner
from .tool_settings import ToolSettings, load_tool_settings, save_tool_settings, tool_settings_path
from .trends import TrendSnapshot, load_or_fetch_trends, trend_cache_path
from .wechat import WeChatClient


BATCH_SIZE = 5
MAX_BATCH_SIZE = 10
CORE_GENERATION_LOGIC = "1000字以内；强实用性；措辞幽默；引用公开数据源；每条都要落到餐饮门店可执行动作。"
KEYWORD_SOURCE_LABEL = "Bing新闻、Bing网页、百度、搜狗微信、头条、抖音公开热榜等公开信息源"


@dataclass(frozen=True)
class PreviewItem:
    publish_date: str
    title: str
    issue_number: int | None
    article_type: str
    topic_name: str
    keywords: list[str]
    draft_media_id: str | None
    output_dir: Path
    archived: bool = False
    focus_keyword: str | None = None
    focus_count: int | None = None
    manual_images: dict[str, str] | None = None
    image_workbench: dict[str, Any] | None = None
    copy_markdown: str = ""
    copy_html: str = ""
    quality_ok: bool = True
    planned_topic: str = ""
    writing_angle: str = ""
    body_preview: str = ""


def create_app() -> Flask:
    app = Flask(__name__)
    settings = load_settings()

    @app.after_request
    def add_api_cors_headers(response: Response) -> Response:
        if request.path.startswith("/api/"):
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return response

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
            keyword_results=_recent_keyword_results(settings),
            archive_view=False,
            settings_saved=request.args.get("settings_saved") == "1",
            generation_error=request.args.get("generation_error") or "",
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
            keyword_results=[],
            archive_view=True,
            settings_saved=False,
            generation_error="",
            image_slots=slot_options(),
        )

    @app.get("/settings")
    def settings_page() -> Response:
        return redirect(url_for("index"))

    @app.post("/settings")
    def save_settings() -> str:
        path = tool_settings_path(settings.output_dir)
        existing = load_tool_settings(path)
        next_settings = ToolSettings(
            article_type=_clean_article_type(request.form.get("article_type")),
            next_issue_number=str(request.form.get("next_issue_number") or "").strip(),
            article_angle=CORE_GENERATION_LOGIC,
            keyword_override=str(request.form.get("keyword_override") or "").strip(),
            image_provider=existing.image_provider,
            openai_api_key=existing.openai_api_key,
            openai_image_model=existing.openai_image_model,
            openai_image_size=existing.openai_image_size,
            openai_image_quality=existing.openai_image_quality,
            huge_profile_prompt=existing.huge_profile_prompt,
            image_style_prompt=existing.image_style_prompt,
        )
        save_tool_settings(path, next_settings)
        return redirect(url_for("index", settings_saved=1))

    @app.post("/generate")
    def generate_batch() -> Response:
        start_date = _parse_date(request.form.get("start_date")) or date.today()
        count = _clamp_count(request.form.get("count"))
        regenerate = request.form.get("regenerate") == "1"
        tool_settings = load_tool_settings(tool_settings_path(settings.output_dir))
        input_keyword = (tool_settings.keyword_override or "").strip()
        if tool_settings.article_type == "hot_interpretation" and not input_keyword:
            return redirect(url_for("index", generation_error="hot_keyword_required"))
        issue_base = _parse_positive_int(tool_settings.next_issue_number)
        plans = topic_planner(
            keyword=input_keyword,
            article_type=tool_settings.article_type,
            count=count,
            seed=int(time.time()) if regenerate else None,
        )
        if not plans:
            return redirect(url_for("index", generation_error="topic_plan_empty"))
        trend_snapshot = None
        if settings.enable_trend_content and not tool_settings.keyword_list:
            try:
                trend_snapshot = _recent_trend_snapshot(settings, start_date=start_date, fetch_missing=False)
            except Exception:
                trend_snapshot = None
        dates: list[str] = []
        generated_metadata: list[dict[str, Any]] = []
        for offset, plan in enumerate(plans[:count]):
            publish_date = start_date + timedelta(days=offset)
            build_daily_article(
                settings,
                publish_date=publish_date,
                upload_draft=False,
                seed=int(time.time()) + offset if regenerate else None,
                trend_snapshot=trend_snapshot,
                trend_keyword=plan.keyword or None,
                issue_number_override=issue_base + offset if issue_base else None,
                topic_plan=plan,
            )
            metadata = _read_metadata(settings, publish_date) or {}
            if _duplicates_existing(metadata, generated_metadata):
                replacement = _replacement_plan(
                    plans=plans,
                    used={item.get("planned_topic", "") for item in generated_metadata},
                    keyword=input_keyword,
                    article_type=tool_settings.article_type,
                    count=count,
                    seed=int(time.time()) + offset + 100,
                )
                if replacement:
                    build_daily_article(
                        settings,
                        publish_date=publish_date,
                        upload_draft=False,
                        seed=int(time.time()) + offset + 200,
                        trend_snapshot=trend_snapshot,
                        trend_keyword=replacement.keyword or None,
                        issue_number_override=issue_base + offset if issue_base else None,
                        topic_plan=replacement,
                    )
                    metadata = _read_metadata(settings, publish_date) or metadata
            generated_metadata.append(metadata)
            dates.append(publish_date.isoformat())
        _write_current_batch(settings, dates)
        if tool_settings.article_type == "ten_lessons":
            _save_next_issue_from_batch(settings, tool_settings, dates)
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

    @app.post("/regenerate/<publish_date>")
    def regenerate_one(publish_date: str) -> Response:
        parsed = _parse_date(publish_date)
        if parsed is None:
            abort(404)
        metadata = _read_metadata(settings, parsed)
        issue_number = metadata.get("issue_number") if metadata else None
        focus_keyword = str(metadata.get("trend_focus_keyword") or "") if metadata else None
        plan = _plan_from_metadata(metadata) if metadata else None
        build_daily_article(
            settings,
            publish_date=parsed,
            upload_draft=False,
            seed=int(time.time()),
            trend_keyword=focus_keyword or None,
            issue_number_override=issue_number if isinstance(issue_number, int) else None,
            topic_plan=plan,
        )
        return redirect(url_for("preview", publish_date=publish_date))

    @app.post("/preview/<publish_date>/cover")
    def upload_cover_image(publish_date: str) -> Response:
        parsed = _parse_date(publish_date)
        if parsed is None:
            abort(404)
        image = request.files.get("image")
        if image is None or not image.filename:
            if request.form.get("return_to") == "index":
                return redirect(url_for("index"))
            return redirect(url_for("preview", publish_date=publish_date))
        metadata = _read_metadata(settings, parsed)
        if not metadata:
            abort(404)
        run_dir = _draft_dir(settings, parsed)
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(image.filename).suffix or ".jpg") as tmp:
            tmp_path = Path(tmp.name)
        image.save(tmp_path)
        try:
            cover_path = save_cover_image(run_dir, tmp_path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
        metadata["cover_image"] = str(cover_path)
        metadata["draft_media_id"] = None
        _write_metadata(settings, parsed, metadata)
        if request.form.get("return_to") == "index":
            return redirect(url_for("index"))
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
        workbench = _workbench_from_metadata(metadata, settings)
        return render_template(
            "preview.html",
            metadata=metadata,
            publish_date=publish_date,
            archived=archived,
            image_workbench=workbench,
            image_slots=slot_options(),
            manual_images=manual_images_from_metadata(metadata),
            copy_markdown=_draft_markdown(metadata),
            copy_html=_draft_copy_html(settings, parsed, metadata, archived=archived),
        )

    @app.get("/outputs/<path:filename>")
    def outputs(filename: str) -> Response:
        return send_from_directory(settings.output_dir, filename)

    @app.get("/export/<publish_date>.<file_type>")
    def export_draft(publish_date: str, file_type: str) -> Response:
        parsed = _parse_date(publish_date)
        if parsed is None or file_type not in {"md", "html"}:
            abort(404)
        archived = request.args.get("archived") == "1"
        metadata = _read_metadata(settings, parsed, archived=archived)
        if not metadata:
            abort(404)
        if file_type == "md":
            content = _draft_markdown(metadata)
            mimetype = "text/markdown; charset=utf-8"
            filename = f"{publish_date}.md"
        else:
            content = _draft_copy_html(settings, parsed, metadata, archived=archived)
            mimetype = "text/html; charset=utf-8"
            filename = f"{publish_date}.html"
        return Response(
            content,
            mimetype=mimetype,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "ok": True,
            "has_wechat_credentials": settings.has_wechat_credentials,
            "output_dir": str(settings.output_dir),
        }

    @app.post("/api/reference-search")
    def api_reference_search() -> Response:
        payload = request.get_json(silent=True) or {}
        keyword = str(payload.get("keyword") or request.form.get("keyword") or "").strip()
        role = str(payload.get("role") or request.form.get("role") or "owner").strip()
        force_refresh = bool(payload.get("force_refresh") or request.form.get("force_refresh"))
        try:
            limit = int(payload.get("limit") or request.form.get("limit") or 6)
        except (TypeError, ValueError):
            limit = 6
        if not keyword:
            return jsonify({"ok": False, "error": "keyword is required"}), 400
        try:
            result = search_reference_articles(
                keyword=keyword,
                role=role,
                limit=limit,
                cache_dir=settings.output_dir.parent / "data",
                force_refresh=force_refresh,
            )
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
        data = result.to_dict()
        data["ok"] = True
        data["reference_text"] = format_references_for_prompt(result.articles)
        return jsonify(data)

    @app.route("/api/reference-search", methods=["OPTIONS"])
    def api_reference_search_options() -> Response:
        response = Response("")
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return response

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


def _parse_positive_int(value: str | None) -> int | None:
    try:
        number = int(str(value or "").strip())
    except ValueError:
        return None
    return number if number > 0 else None


def _clamp_count(value: str | None) -> int:
    try:
        count = int(str(value or "").strip())
    except ValueError:
        return BATCH_SIZE
    return max(1, min(MAX_BATCH_SIZE, count))


def _clean_article_type(value: str | None) -> str:
    article_type = str(value or "").strip()
    if article_type in {"ten_lessons", "hot_interpretation", "methodology"}:
        return article_type
    return "ten_lessons"


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
        article_type=str(metadata.get("article_type") or metadata.get("tool_settings", {}).get("article_type") or ""),
        topic_name=str(metadata.get("topic_name", "")),
        keywords=[str(item) for item in metadata.get("trend_keywords", [])],
        draft_media_id=metadata.get("draft_media_id"),
        output_dir=_draft_dir(settings, parsed, archived=archived),
        archived=archived,
        focus_keyword=str(metadata.get("trend_focus_keyword") or "") or None,
        focus_count=_focus_count(metadata),
        manual_images=manual_images_from_metadata(metadata),
        image_workbench=_workbench_from_metadata(metadata, settings),
        copy_markdown=_draft_markdown(metadata),
        copy_html=_draft_copy_html(settings, parsed, metadata, archived=archived),
        quality_ok=_quality_ok(metadata),
        planned_topic=str(metadata.get("planned_topic") or metadata.get("topic_name") or ""),
        writing_angle=str(metadata.get("writing_angle") or ""),
        body_preview=_body_preview(metadata),
    )


def _workbench_from_metadata(metadata: dict[str, Any], settings: Settings) -> dict[str, Any]:
    workbench = metadata.get("image_prompt_workbench")
    if isinstance(workbench, dict) and len(workbench.get("groups", [])) == 1:
        return workbench
    return build_workbench_from_metadata(metadata, brand_name=settings.brand_name)


def _focus_count(metadata: dict[str, Any]) -> int | None:
    keyword = str(metadata.get("trend_focus_keyword") or "")
    counts = metadata.get("trend_keyword_counts")
    if not keyword or not isinstance(counts, dict):
        return None
    value = counts.get(keyword)
    return value if isinstance(value, int) else None


def _quality_ok(metadata: dict[str, Any]) -> bool:
    checks = metadata.get("quality_checks")
    if not isinstance(checks, list):
        return True
    return all(bool(item.get("ok")) for item in checks if isinstance(item, dict))


def _body_preview(metadata: dict[str, Any]) -> str:
    parts = [str(metadata.get("intro") or "")]
    for item in metadata.get("advices", []):
        if isinstance(item, dict):
            parts.append(str(item.get("title") or ""))
            parts.append(str(item.get("body") or ""))
            if len("".join(parts)) > 120:
                break
    text = " ".join(part.strip() for part in parts if part.strip())
    return text[:150] + ("..." if len(text) > 150 else "")


def _plan_from_metadata(metadata: dict[str, Any] | None) -> TopicPlan | None:
    if not metadata:
        return None
    topic = str(metadata.get("planned_topic") or metadata.get("topic_name") or "").strip()
    angle = str(metadata.get("writing_angle") or "").strip()
    if not topic or not angle:
        return None
    return TopicPlan(
        topic=topic,
        angle=angle,
        target_reader=str(metadata.get("target_reader") or "中小餐饮老板、餐饮店长、餐饮创业者"),
        avoid_repeat_point=str(metadata.get("avoid_repeat_point") or "不要复用其他草稿的小标题、核心观点和胡哥总结"),
        keyword=str(metadata.get("trend_focus_keyword") or ""),
    )


def _duplicates_existing(metadata: dict[str, Any], existing: list[dict[str, Any]]) -> bool:
    if not metadata:
        return False
    current_title = _fingerprint(str(metadata.get("title") or ""))
    current_topic = _fingerprint(str(metadata.get("planned_topic") or metadata.get("topic_name") or ""))
    current_heads = {
        _fingerprint(str(item.get("title") or ""))
        for item in metadata.get("advices", [])
        if isinstance(item, dict)
    }
    current_summary = _fingerprint(str(metadata.get("conclusion") or ""))
    for item in existing:
        other_title = _fingerprint(str(item.get("title") or ""))
        other_topic = _fingerprint(str(item.get("planned_topic") or item.get("topic_name") or ""))
        other_heads = {
            _fingerprint(str(advice.get("title") or ""))
            for advice in item.get("advices", [])
            if isinstance(advice, dict)
        }
        other_summary = _fingerprint(str(item.get("conclusion") or ""))
        if current_title and current_title == other_title:
            return True
        if current_topic and current_topic == other_topic:
            return True
        if current_summary and current_summary == other_summary:
            return True
        if len(current_heads & other_heads) >= 2:
            return True
    return False


def _replacement_plan(
    *,
    plans: list[TopicPlan],
    used: set[object],
    keyword: str,
    article_type: str,
    count: int,
    seed: int,
) -> TopicPlan | None:
    for plan in topic_planner(keyword=keyword, article_type=article_type, count=10, seed=seed):
        if plan.topic not in used and all(plan.topic != existing.topic for existing in plans):
            return plan
    for plan in topic_planner(keyword=keyword, article_type=article_type, count=max(10, count), seed=seed + 1):
        if plan.topic not in used:
            return plan
    return None


def _fingerprint(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


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
    html = render_article_html(
        article,
        brand_name=settings.brand_name,
        inline_images={},
        output_path=run_dir / "article.html",
    )
    image_check = ensure_article_images(html, html_path=run_dir / "article.html")
    metadata["quality_checks"] = check_article_quality(article, html)
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


def _save_next_issue_from_batch(settings: Settings, tool_settings: ToolSettings, dates: list[str]) -> None:
    issue_numbers: list[int] = []
    for value in dates:
        parsed = _parse_date(value)
        if parsed is None:
            continue
        metadata = _read_metadata(settings, parsed)
        issue = metadata.get("issue_number") if metadata else None
        if isinstance(issue, int):
            issue_numbers.append(issue)
    if not issue_numbers:
        return
    save_tool_settings(
        tool_settings_path(settings.output_dir),
        ToolSettings(
            article_type=tool_settings.article_type,
            next_issue_number=str(max(issue_numbers) + 1),
            article_angle=CORE_GENERATION_LOGIC,
            keyword_override=tool_settings.keyword_override,
            image_provider=tool_settings.image_provider,
            openai_api_key=tool_settings.openai_api_key,
            openai_image_model=tool_settings.openai_image_model,
            openai_image_size=tool_settings.openai_image_size,
            openai_image_quality=tool_settings.openai_image_quality,
            huge_profile_prompt=tool_settings.huge_profile_prompt,
            image_style_prompt=tool_settings.image_style_prompt,
        ),
    )


def _draft_markdown(metadata: dict[str, Any]) -> str:
    lines = [
        f"# {metadata.get('title', '')}",
        "",
        "【图片插入位：请在这里插入本期配图】",
        "",
        str(metadata.get("intro", "")),
        "",
    ]
    for item in metadata.get("advices", []):
        if not isinstance(item, dict):
            continue
        lines.extend(
            [
                f"{item.get('index', '')}. {item.get('title', '')}",
                str(item.get("body", "")),
                "",
            ]
        )
    lines.extend(["总结：", str(metadata.get("conclusion", ""))])
    sources = [str(item) for item in metadata.get("trend_sources", []) if item]
    if sources:
        lines.extend(["", "公开数据源参考：", *[f"- {item}" for item in sources[:3]]])
    return "\n".join(lines).strip()


def _draft_copy_html(settings: Settings, publish_date: date, metadata: dict[str, Any], *, archived: bool = False) -> str:
    html_path = _draft_dir(settings, publish_date, archived=archived) / "article.html"
    body = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
    return f"<h1>{metadata.get('title', '')}</h1>\n{body}".strip()


def _recent_keyword_results(settings: Settings) -> list[dict[str, object]]:
    keywords: list[str] = []
    try:
        snapshot = _recent_trend_snapshot(settings, start_date=date.today(), fetch_missing=False)
        counter = Counter(snapshot.keyword_counts or {})
        source_count = len(snapshot.source_titles)
        keywords = snapshot.keywords
    except Exception:
        counter = Counter()
        source_count = 0
    if not counter:
        counter.update({keyword: 1 for keyword in keywords})

    if not counter:
        counter.update({
            "外卖": 8,
            "复购": 7,
            "食品安全": 6,
            "门店成本": 5,
            "茶饮": 4,
        })

    total = sum(counter.values()) or 1
    return [
        {
            "keyword": keyword,
            "count": count,
            "mention_rate": round(count / total * 100, 1),
            "source_label": KEYWORD_SOURCE_LABEL,
            "source_count": source_count,
        }
        for keyword, count in counter.most_common(10)
    ]


def _recent_trend_snapshot(settings: Settings, *, start_date: date, fetch_missing: bool = True) -> TrendSnapshot:
    counter: Counter[str] = Counter()
    source_titles: list[str] = []
    summaries: list[str] = []
    cache = _read_trend_cache(settings)
    for offset in range(5):
        publish_date = start_date - timedelta(days=offset)
        try:
            target_date = publish_date - timedelta(days=1)
            cached = cache.get(target_date.isoformat())
            if cached and isinstance(cached, dict):
                snapshot = TrendSnapshot(
                    target_date=target_date,
                    keywords=[str(item) for item in cached.get("keywords", [])],
                    summary=str(cached.get("summary", "")),
                    source_titles=[str(item) for item in cached.get("source_titles", [])],
                    keyword_counts={
                        str(key): int(value)
                        for key, value in (cached.get("keyword_counts", {}) or {}).items()
                        if isinstance(value, int)
                    },
                )
            elif fetch_missing:
                snapshot = load_or_fetch_trends(output_dir=settings.output_dir, publish_date=publish_date)
            else:
                continue
        except Exception:
            continue
        source_titles.extend(snapshot.source_titles)
        if snapshot.summary:
            summaries.append(snapshot.summary)
        if snapshot.keyword_counts:
            counter.update(snapshot.keyword_counts)
        else:
            counter.update(snapshot.keywords)

    if not counter:
        counter.update({
            "外卖": 8,
            "复购": 7,
            "食品安全": 6,
            "门店成本": 5,
            "茶饮": 4,
        })
    keywords = [keyword for keyword, _ in counter.most_common(10)]
    unique_sources = list(dict.fromkeys(source_titles))
    summary = "近5天公开信息源餐饮关键词提及率靠前：" + "、".join(keywords[:5]) + "。"
    if summaries:
        summary += " " + summaries[0]
    return TrendSnapshot(
        target_date=start_date - timedelta(days=1),
        keywords=keywords,
        summary=summary,
        source_titles=unique_sources[:30],
        keyword_counts=dict(counter.most_common(20)),
    )


def _read_trend_cache(settings: Settings) -> dict[str, Any]:
    path = trend_cache_path(settings.output_dir)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
