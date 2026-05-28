from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any

import requests


API_BASE = "https://api.weixin.qq.com"
MAX_TITLE_CHARS = 64


class WeChatApiError(RuntimeError):
    pass


@dataclass
class WeChatClient:
    app_id: str
    app_secret: str
    token_cache_path: Path = Path("token_cache.json")

    def access_token(self) -> str:
        cached = self._read_cached_token()
        if cached:
            return cached

        response = requests.get(
            f"{API_BASE}/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": self.app_id,
                "secret": self.app_secret,
            },
            timeout=30,
        )
        data = self._json(response)
        if "access_token" not in data:
            raise WeChatApiError(f"Failed to get access token: {data}")
        expires_at = int(time.time()) + int(data.get("expires_in", 7200)) - 300
        self.token_cache_path.write_text(
            json.dumps(
                {"access_token": data["access_token"], "expires_at": expires_at},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return str(data["access_token"])

    def upload_content_image(self, image_path: Path) -> str:
        with image_path.open("rb") as handle:
            response = requests.post(
                f"{API_BASE}/cgi-bin/media/uploadimg",
                params={"access_token": self.access_token()},
                files={"media": (image_path.name, handle, "image/jpeg")},
                timeout=60,
            )
        data = self._json(response)
        if "url" not in data:
            raise WeChatApiError(f"Failed to upload content image: {data}")
        return str(data["url"])

    def upload_cover_thumb(self, image_path: Path) -> str:
        with image_path.open("rb") as handle:
            response = requests.post(
                f"{API_BASE}/cgi-bin/material/add_material",
                params={"access_token": self.access_token(), "type": "thumb"},
                files={"media": (image_path.name, handle, "image/jpeg")},
                timeout=60,
            )
        data = self._json(response)
        if "media_id" not in data:
            raise WeChatApiError(f"Failed to upload cover thumb: {data}")
        return str(data["media_id"])

    def add_draft(
        self,
        *,
        title: str,
        author: str,
        digest: str,
        content: str,
        thumb_media_id: str,
        content_source_url: str = "",
    ) -> str:
        title = _limit_text(title, MAX_TITLE_CHARS)
        payload: dict[str, Any] = {
            "articles": [
                {
                    "title": title,
                    "author": author,
                    "digest": digest[:120],
                    "content": content,
                    "content_source_url": content_source_url,
                    "thumb_media_id": thumb_media_id,
                    "need_open_comment": 0,
                    "only_fans_can_comment": 0,
                }
            ]
        }
        response = requests.post(
            f"{API_BASE}/cgi-bin/draft/add",
            params={"access_token": self.access_token()},
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=60,
        )
        data = self._json(response)
        if "media_id" not in data:
            raise WeChatApiError(f"Failed to add draft: {data}")
        return str(data["media_id"])

    def _read_cached_token(self) -> str | None:
        if not self.token_cache_path.exists():
            return None
        try:
            data = json.loads(self.token_cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if int(data.get("expires_at", 0)) <= int(time.time()):
            return None
        token = data.get("access_token")
        return str(token) if token else None

    @staticmethod
    def _json(response: requests.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise WeChatApiError(f"Non-JSON response: {response.text[:500]}") from exc
        errcode = data.get("errcode")
        if errcode not in (None, 0):
            raise WeChatApiError(f"WeChat API error {errcode}: {data}")
        return data


def _limit_text(value: str, max_chars: int) -> str:
    value = value.strip()
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "…"
