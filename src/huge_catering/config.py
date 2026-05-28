from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    brand_name: str
    column_name: str
    author_name: str
    output_dir: Path
    topic_library_path: Path
    start_issue_number: int
    enable_trend_content: bool
    wechat_app_id: str | None
    wechat_app_secret: str | None

    @property
    def has_wechat_credentials(self) -> bool:
        return bool(self.wechat_app_id and self.wechat_app_secret)


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        brand_name=os.getenv("BRAND_NAME", "胡哥说餐饮"),
        column_name=os.getenv("COLUMN_NAME", "餐饮要赚钱 听我10句劝"),
        author_name=os.getenv("AUTHOR_NAME", "胡哥"),
        output_dir=Path(os.getenv("OUTPUT_DIR", "outputs")).resolve(),
        topic_library_path=Path(os.getenv("TOPIC_LIBRARY", "data/topic_library.json")).resolve(),
        start_issue_number=int(os.getenv("START_ISSUE_NUMBER", "229")),
        enable_trend_content=os.getenv("ENABLE_TREND_CONTENT", "true").lower() not in {
            "0",
            "false",
            "no",
        },
        wechat_app_id=os.getenv("WECHAT_APP_ID") or None,
        wechat_app_secret=os.getenv("WECHAT_APP_SECRET") or None,
    )
