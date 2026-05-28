from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HistoryEntry:
    publish_date: date
    topic_id: str
    title: str
    issue_number: int | None = None


def read_history(path: Path) -> list[HistoryEntry]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    entries: list[HistoryEntry] = []
    for item in raw if isinstance(raw, list) else []:
        try:
            entries.append(
                HistoryEntry(
                    publish_date=datetime.strptime(item["publish_date"], "%Y-%m-%d").date(),
                    topic_id=str(item["topic_id"]),
                    title=str(item["title"]),
                    issue_number=_optional_int(item.get("issue_number")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return entries


def history_path(output_dir: Path) -> Path:
    return output_dir.parent / "data" / "publish_history.json"


def used_topic_for_date(entries: list[HistoryEntry], publish_date: date) -> str | None:
    for entry in entries:
        if entry.publish_date == publish_date:
            return entry.topic_id
    return None


def issue_number_for_date(
    entries: list[HistoryEntry],
    publish_date: date,
    *,
    start_issue_number: int,
) -> int:
    sorted_entries = sorted(entries, key=lambda item: item.publish_date)
    issue_by_date: dict[date, int] = {}
    next_issue_number = start_issue_number

    for entry in sorted_entries:
        if entry.issue_number is not None:
            issue_by_date[entry.publish_date] = entry.issue_number
            next_issue_number = max(next_issue_number, entry.issue_number + 1)
        elif entry.publish_date not in issue_by_date:
            issue_by_date[entry.publish_date] = next_issue_number
            next_issue_number += 1

    if publish_date in issue_by_date:
        return issue_by_date[publish_date]
    return next_issue_number


def recently_used_topic_ids(entries: list[HistoryEntry], days: int = 45) -> set[str]:
    recent = sorted(entries, key=lambda item: item.publish_date, reverse=True)[:days]
    return {item.topic_id for item in recent}


def record_history(
    path: Path,
    *,
    publish_date: date,
    topic_id: str,
    title: str,
    issue_number: int,
) -> None:
    entries = read_history(path)
    updated: list[dict[str, Any]] = [
        {
            "publish_date": entry.publish_date.isoformat(),
            "topic_id": entry.topic_id,
            "title": entry.title,
            "issue_number": entry.issue_number,
        }
        for entry in entries
        if entry.publish_date != publish_date
    ]
    updated.append(
        {
            "publish_date": publish_date.isoformat(),
            "topic_id": topic_id,
            "title": title,
            "issue_number": issue_number,
        }
    )
    updated.sort(key=lambda item: item["publish_date"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")


def _optional_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
