from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Advice:
    index: int
    title: str
    body: str


@dataclass(frozen=True)
class Article:
    title: str
    digest: str
    author: str
    publish_date: date
    topic_id: str
    topic_name: str
    issue_number: int
    intro: str
    advices: list[Advice]
    conclusion: str
    trend_keywords: list[str] = field(default_factory=list)
    trend_summary: str = ""
    source_url: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return self.publish_date.strftime("%Y%m%d")
