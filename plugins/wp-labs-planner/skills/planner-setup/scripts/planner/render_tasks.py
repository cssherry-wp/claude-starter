"""Render Sheets-derived todos as Obsidian Tasks; dedup against existing vault tasks."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from planner.collectors.gsheet import CompletedItem, OpenItem, normalize_text
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


_OPEN_HEADING = "Open Items"
_STUB = "## Notes\n\n## Open Items\n\n## TODO\n"


def _ensure_heading(vault: Any, path: str, heading: str) -> None:
    """Ensure *path* exists and contains a `## {heading}` section to patch into.

    Creates the note from the stub when absent. When the note already exists but
    omits the heading — e.g. a daily note built from a Daily Notes template that
    lacks it — appends the heading so a following patch_heading can target it.

    Args:
        vault: Vault object with exists(), read(), and write() methods.
        path: Path to the note file.
        heading: The level-2 heading (without the leading '## ') that must exist.
    """
    if not vault.exists(path):
        vault.write(path, _STUB)
        return
    body = vault.read(path)
    if re.search(rf"^## {re.escape(heading)}[ \t]*$", body, re.MULTILINE):
        return
    separator = "" if body.endswith("\n") else "\n"
    vault.write(path, f"{body}{separator}\n## {heading}\n")


def _reconcile(vault: Any, ref: TaskRef, item: OpenItem, end: date) -> None:
    """Rewrite the matched task line's signifiers in place, preserving checkbox state.

    Args:
        vault: Vault object with read() and write() methods.
        ref: Reference to the existing task.
        item: The open item to reconcile with.
        end: The Sunday end date of the week.
    """
    body = vault.read(ref.path)
    lines = body.splitlines()
    key = normalize_text(item.text)
    desired = open_task_line(item, end)
    for i, line in enumerate(lines):
        if "[" not in line or normalize_text(line) != key:
            continue
        rebuilt = ("- [x]" + desired[len("- [ ]"):]) if "[x]" in line.lower() else desired
        if rebuilt != line:
            lines[i] = rebuilt
            tail = "\n" if body.endswith("\n") else ""
            vault.write(ref.path, "\n".join(lines) + tail)
        return


def apply_open_items(vault: Any, daily_dir: str, items: list[OpenItem], today: date,
                     index: dict[str, TaskRef]) -> None:
    """Append new open items under today's '## Open Items'; reconcile existing matches.

    Args:
        vault: Vault object with exists(), write(), read(), and patch_heading() methods.
        daily_dir: Directory path for daily notes (e.g. "daily").
        items: List of open items to apply.
        today: Today's date.
        index: Dictionary mapping normalized task text to TaskRef for deduplication.
    """
    end = week_end(today)
    today_path = f"{daily_dir}/{today.isoformat()}.md"
    new_lines: list[str] = []
    for item in items:
        ref = index.get(normalize_text(item.text))
        if ref is None:
            new_lines.append(open_task_line(item, end))
        else:
            _reconcile(vault, ref, item, end)
    if new_lines:
        _ensure_heading(vault, today_path, _OPEN_HEADING)
        vault.patch_heading(today_path, _OPEN_HEADING, "\n".join(new_lines), operation="append")


def _llm_task_line(text: str, priority: str) -> str:
    """Build a '- [ ]' task line for an LLM-synthesized task.

    Args:
        text: Task text, already stripped.
        priority: Priority level string passed to priority_emoji.

    Returns:
        Formatted task line with trailing emoji if priority is known.
    """
    return f"- [ ] {text} {priority_emoji(priority)}".rstrip()


def apply_llm_tasks(vault: Any, daily_dir: str, new_tasks: list[dict],
                    today: date, index: dict[str, TaskRef],
                    claimed_keys: set[str]) -> None:
    """Append LLM-synthesized tasks to today's '## Open Items', deduped against vault+sheet.

    Skips tasks already in *index* (vault) or *claimed_keys* (Sheet open items).
    Deduplicates identical tasks within a single batch. Does not mutate index or
    claimed_keys. Makes no patch call when all tasks are filtered out.

    Args:
        vault: Vault object with exists(), write(), and patch_heading() methods.
        daily_dir: Directory path for daily notes (e.g. "daily").
        new_tasks: List of task dicts with "text" and "priority" keys from LLM synthesis.
        today: Today's date.
        index: Existing vault task index keyed by normalized text.
        claimed_keys: Normalized keys already claimed by Sheet open items.
    """
    today_path = f"{daily_dir}/{today.isoformat()}.md"
    seen: set[str] = set()
    new_lines: list[str] = []
    for task in new_tasks:
        text = task.get("text", "").strip()
        if not text:
            continue
        key = normalize_text(text)
        if key in index or key in claimed_keys or key in seen:
            continue
        seen.add(key)
        new_lines.append(_llm_task_line(text, task.get("priority", "")))
    if new_lines:
        _ensure_heading(vault, today_path, _OPEN_HEADING)
        vault.patch_heading(today_path, _OPEN_HEADING, "\n".join(new_lines), operation="append")


def _duration_suffix(item: CompletedItem) -> str:
    """Return a duration suffix for a completed item, or empty string if unknown.

    Args:
        item: The completed item with started_at and completed_at times.

    Returns:
        A string like " (12m)" or " (1h 30m)" if duration is positive, or "" otherwise.
    """
    if not item.started_at:
        return ""
    minutes = int((item.completed_at - item.started_at).total_seconds() // 60)
    if minutes <= 0:
        return ""
    hours, mins = divmod(minutes, 60)
    label = f"{hours}h {mins}m" if hours else f"{mins}m"
    return f" ({label})"


def apply_completed_items(vault: Any, daily_dir: str, items: list[CompletedItem],
                          index: dict[str, TaskRef]) -> None:
    """Backfill undocumented completed items into their completion-date daily notes.

    Args:
        vault: Vault object with exists(), write(), and patch_heading() methods.
        daily_dir: Directory path for daily notes (e.g. "daily").
        items: List of completed items to backfill.
        index: Dictionary mapping normalized task text to TaskRef for deduplication.
    """
    for item in items:
        if normalize_text(item.text) in index:
            continue
        day = item.completed_at.date()
        path = f"{daily_dir}/{day.isoformat()}.md"
        _ensure_heading(vault, path, "TODO")
        line = f"- [x] {item.text} ✅ {day.isoformat()}{_duration_suffix(item)}"
        vault.patch_heading(path, "TODO", line, operation="append")
