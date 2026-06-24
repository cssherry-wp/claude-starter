"""Render Sheets-derived todos as Obsidian Tasks; dedup against existing vault tasks."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from planner.collectors.gsheet import OpenItem, normalize_text
from planner.errors import priority_emoji

log = logging.getLogger(__name__)

_STATUS_PRIORITY = {"on notice": "high", "waiting": "low"}
_TASK_DQL = (
    'TABLE WITHOUT ID t.text AS text, file.path AS path, t.completed AS completed '
    'FROM -"zz-Templates" FLATTEN file.tasks AS t'
)


def week_end(today: date) -> date:
    """Return the Sunday of today's week (Monday-started week)."""
    return today + timedelta(days=6 - today.weekday())


def status_slug(status: str) -> str:
    """Return a tag-safe kebab slug for a status (e.g. 'On Notice' -> 'on-notice')."""
    return "-".join(status.lower().split())


def open_task_line(item: OpenItem, end: date) -> str:
    """Build an Obsidian Tasks '- [ ]' line for an open item."""
    parts = [f"- [ ] {item.text}"]
    status = item.status.lower()
    priority = _STATUS_PRIORITY.get(status, "")
    if priority:
        parts.append(priority_emoji(priority))
    if status == "on notice":
        parts.append(f"📅 {end.isoformat()}")
    if status == "started" and item.started_at:
        parts.append(f"🛫 {item.started_at.date().isoformat()}")
    if item.status:
        parts.append(f"#status/{status_slug(item.status)}")
    if item.carry_over_weeks:
        parts.append(f"(carried {item.carry_over_weeks}w)")
    return " ".join(parts)


@dataclass
class TaskRef:
    path: str
    text: str
    completed: bool


def _row_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def existing_task_index(vault: Any) -> dict[str, TaskRef]:
    """Return existing vault tasks keyed by normalized text via a Dataview query.

    Returns an empty dict when the vault exposes no search_query or the query fails
    (dedup degrades to off — never aborts the run).
    """
    search = getattr(vault, "search_query", None)
    if search is None:
        return {}
    try:
        rows = search({"queryType": "dataview", "dql": _TASK_DQL})
    except Exception as exc:  # noqa: BLE001 — dedup must degrade, not abort
        log.warning("dataview task query failed: %s", exc)
        return {}
    index: dict[str, TaskRef] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        text = _row_value(row, "text")
        if not text:
            continue
        index[normalize_text(str(text))] = TaskRef(
            path=str(_row_value(row, "path") or ""),
            text=str(text),
            completed=bool(_row_value(row, "completed")),
        )
    return index
