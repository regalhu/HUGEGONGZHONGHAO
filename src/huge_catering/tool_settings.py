from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path


@dataclass(frozen=True)
class ToolSettings:
    article_angle: str = "把热点拆成门店今天能执行的动作"
    keyword_override: str = ""
    title_style: str = "hot_warning"
    image_provider: str = "local"
    openai_api_key: str = ""
    openai_image_model: str = "gpt-image-1"
    openai_image_size: str = "1024x1024"
    openai_image_quality: str = "low"
    huge_profile_prompt: str = "胡哥是40岁左右的中国餐饮经营顾问，短发，深色夹克，表情笃定亲和"
    image_style_prompt: str = "公众号漫画插画，清晰明亮，适合餐饮老板阅读，避免大段文字"

    @property
    def keyword_list(self) -> list[str]:
        return [
            item.strip()
            for item in self.keyword_override.replace("，", ",").split(",")
            if item.strip()
        ][:5]

    @property
    def uses_openai_image(self) -> bool:
        return self.image_provider == "openai" and bool(self.openai_api_key.strip())

    def masked(self) -> "ToolSettings":
        if not self.openai_api_key:
            return self
        return replace_setting(self, openai_api_key="已保存，不在页面显示")


def tool_settings_path(output_dir: Path) -> Path:
    return output_dir.parent / "data" / "tool_settings.json"


def load_tool_settings(path: Path) -> ToolSettings:
    env_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not path.exists():
        return ToolSettings(openai_api_key=env_api_key)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ToolSettings()
    if not isinstance(raw, dict):
        return ToolSettings()
    fields = {field: raw.get(field) for field in ToolSettings.__dataclass_fields__}
    clean = {key: value for key, value in fields.items() if isinstance(value, str)}
    loaded = ToolSettings(**clean)
    if env_api_key and not loaded.openai_api_key:
        return replace_setting(loaded, openai_api_key=env_api_key)
    return loaded


def save_tool_settings(path: Path, settings: ToolSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")


def replace_setting(settings: ToolSettings, **changes: str) -> ToolSettings:
    values = asdict(settings)
    values.update({key: value for key, value in changes.items() if key in values})
    return ToolSettings(**values)
