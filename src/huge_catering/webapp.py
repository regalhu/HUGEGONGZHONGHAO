from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
from typing import Any

from flask import Flask, Response, abort, redirect, render_template, request, send_from_directory, url_for

from .config import Settings, load_settings
from .pipeline import build_daily_article
from .tool_settings import ToolSettings, load_tool_settings, replace_setting, save_tool_settings, tool_settings_path


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
        )

    @app.get("/settings")
    def settings_page() -> str:
        tool_settings = load_tool_settings(tool_settings_path(settings.output_dir))
        return render_template("settings.html", settings=tool_settings.masked(), saved=False)

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
        return render_template("settings.html", settings=next_settings.masked(), saved=True)

    @app.post("/generate")
    def generate_batch() -> Response:
        start_date = _parse_date(request.form.get("start_date")) or date.today()
        count = int(request.form.get("count") or BATCH_SIZE)
        dates: list[str] = []
        for offset in range(count):
            publish_date = start_date + timedelta(days=offset)
            build_daily_article(settings, publish_date=publish_date, upload_draft=False)
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
            build_daily_article(settings, publish_date=parsed, upload_draft=True)
        return redirect(url_for("preview", publish_date=publish_date))

    @app.get("/preview/<publish_date>")
    def preview(publish_date: str) -> str:
        parsed = _parse_date(publish_date)
        if parsed is None:
            abort(404)
        metadata = _read_metadata(settings, parsed)
        if not metadata:
            abort(404)
        return render_template("preview.html", metadata=metadata, publish_date=publish_date)

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


def _read_metadata(settings: Settings, publish_date: date) -> dict[str, Any] | None:
    path = settings.output_dir / publish_date.isoformat() / "metadata.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _preview_item(settings: Settings, publish_date: str) -> PreviewItem | None:
    parsed = _parse_date(publish_date)
    if parsed is None:
        return None
    metadata = _read_metadata(settings, parsed)
    if not metadata:
        return None
    return PreviewItem(
        publish_date=publish_date,
        title=str(metadata.get("title", "")),
        issue_number=metadata.get("issue_number"),
        topic_name=str(metadata.get("topic_name", "")),
        keywords=[str(item) for item in metadata.get("trend_keywords", [])],
        draft_media_id=metadata.get("draft_media_id"),
        output_dir=settings.output_dir / publish_date,
    )


if __name__ == "__main__":
    raise SystemExit(main())
