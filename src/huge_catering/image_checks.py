from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from urllib.parse import urlparse


ALLOWED_REMOTE_IMAGE_HOSTS = {
    "mmbiz.qpic.cn",
    "mmbiz.qlogo.cn",
    "res.wx.qq.com",
}


@dataclass(frozen=True)
class ImageCheckResult:
    ok: bool
    local_images: list[str]
    remote_images: list[str]
    errors: list[str]


def validate_article_images(html: str, *, html_path: Path) -> ImageCheckResult:
    local_images: list[str] = []
    remote_images: list[str] = []
    errors: list[str] = []

    for src in _img_sources(html):
        parsed = urlparse(src)
        if parsed.scheme in {"http", "https"}:
            host = parsed.netloc.lower()
            remote_images.append(src)
            if host not in ALLOWED_REMOTE_IMAGE_HOSTS:
                errors.append(f"不允许的外部图片链接：{src}")
            continue

        if parsed.scheme and parsed.scheme not in {"", "file"}:
            errors.append(f"不支持的图片链接格式：{src}")
            continue

        image_path = (html_path.parent / src).resolve()
        local_images.append(str(image_path))
        if not image_path.exists():
            errors.append(f"本地图片不存在：{image_path}")
        elif image_path.stat().st_size <= 0:
            errors.append(f"本地图片为空：{image_path}")

    if not local_images and not remote_images:
        errors.append("文章正文里没有检测到图片。")

    return ImageCheckResult(
        ok=not errors,
        local_images=local_images,
        remote_images=remote_images,
        errors=errors,
    )


def ensure_article_images(html: str, *, html_path: Path) -> ImageCheckResult:
    result = validate_article_images(html, html_path=html_path)
    if not result.ok:
        raise ValueError("文章图片检查失败：" + "；".join(result.errors))
    return result


def _img_sources(html: str) -> list[str]:
    sources: list[str] = []
    for match in re.findall(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", html, flags=re.I):
        sources.append(match.strip())
    return sources
