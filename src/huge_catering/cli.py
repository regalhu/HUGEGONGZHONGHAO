from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path
import sys

from .config import load_settings
from .pipeline import build_daily_article


def _parse_date(value: str | None) -> date:
    if not value:
        return date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="huge-wechat",
        description="Generate 胡哥说餐饮 daily article assets and optionally upload a WeChat draft.",
    )
    parser.add_argument(
        "--date",
        help="Publish date in YYYY-MM-DD. Defaults to today.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Optional random seed for reproducible advice selection.",
    )
    parser.add_argument(
        "--upload-draft",
        action="store_true",
        help="Upload images and create a WeChat Official Account draft.",
    )

    args = parser.parse_args(argv)
    settings = load_settings()
    result = build_daily_article(
        settings,
        publish_date=_parse_date(args.date),
        upload_draft=args.upload_draft,
        seed=args.seed,
    )

    print("生成完成")
    print(f"输出目录: {result.output_dir}")
    print(f"文章 HTML: {result.article_html}")
    print(f"封面图: {result.cover_image}")
    print(f"文中图: {result.inline_image}")
    print(f"元数据: {result.metadata_json}")
    if result.draft_media_id:
        print(f"公众号草稿 media_id: {result.draft_media_id}")
    else:
        print("未上传草稿。如需上传，请配置 .env 后加 --upload-draft。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
