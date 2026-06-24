"""Google Sheets collector: parse the Overview tab into open/completed todos."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime

log = logging.getLogger(__name__)

_LEADING_DASH_RE = re.compile(r"^(?:-\s*)+")
_ANNOT_RE = re.compile(r"\(([A-Za-z][A-Za-z ]*?):\s*([^)]*)\)")
_STATUS_TAG_RE = re.compile(r"#status/\S+")
_PRIORITY_RE = re.compile(r"[🔺⏫🔼🔽⏬]")
_DATED_SIGNIFIER_RE = re.compile(r"[📅🛫⏳➕✅]\s*\d{4}-\d{2}-\d{2}")
_CHECKBOX_RE = re.compile(r"-\s*\[[ xX]\]")
_DATE_FMT = "%m/%d/%Y, %I:%M:%S %p"


@dataclass
class OpenItem:
    """An open todo item from a Sheets row."""

    text: str
    status: str
    carry_over_weeks: int
    started_at: datetime | None


@dataclass
class CompletedItem:
    """A completed todo item from a Sheets row."""

    text: str
    completed_at: datetime
    started_at: datetime | None


def _parse_dt(raw: str) -> datetime | None:
    """Parse a date string in _DATE_FMT format, or return None if invalid."""
    try:
        return datetime.strptime(raw.strip(), _DATE_FMT)
    except ValueError:
        return None


def _annotations(text: str) -> list[tuple[str, datetime | None]]:
    """Return (status word, parsed datetime) for each trailing (Word: date) annotation."""
    return [(m.group(1).strip(), _parse_dt(m.group(2))) for m in _ANNOT_RE.finditer(text)]


def _split_dashes(line: str) -> tuple[int, str]:
    """Return (leading dash count, remaining text)."""
    m = _LEADING_DASH_RE.match(line)
    if not m:
        return 0, line
    return line[: m.end()].count("-"), line[m.end() :]


def _annotation_date(annots: list[tuple[str, datetime | None]], word: str) -> datetime | None:
    """Extract the datetime for a given annotation word (case-insensitive)."""
    return next((dt for w, dt in annots if w.lower() == word and dt), None)


def parse_open_line(line: str) -> OpenItem | None:
    """Parse one 'Remaining items' line into an OpenItem, or None if blank/unparseable.

    Args:
        line: A line from the 'Remaining items' section of Sheets.

    Returns:
        An OpenItem with extracted text, status, carryover weeks, and start date;
        or None if the line is blank or has no text after stripping annotations.
    """
    stripped = line.strip()
    if not stripped:
        return None
    dashes, body = _split_dashes(stripped)
    annots = _annotations(body)
    text = _ANNOT_RE.sub("", body).strip()
    if not text:
        return None
    status = annots[-1][0] if annots else ""
    return OpenItem(
        text=text,
        status=status,
        carry_over_weeks=dashes,
        started_at=_annotation_date(annots, "started"),
    )


def parse_completed_line(line: str) -> CompletedItem | None:
    """Parse one 'Completed:' line into a CompletedItem, or None if no completion date.

    Args:
        line: A line from the 'Completed:' section of Sheets.

    Returns:
        A CompletedItem with extracted text, completion date, and start date;
        or None if the line is blank or lacks a Completed annotation.
    """
    stripped = line.strip()
    if not stripped:
        return None
    _, body = _split_dashes(stripped)
    annots = _annotations(body)
    text = _ANNOT_RE.sub("", body).strip()
    completed = next((dt for w, dt in reversed(annots) if w.lower() == "completed" and dt), None)
    if not text or completed is None:
        return None
    return CompletedItem(
        text=text,
        completed_at=completed,
        started_at=_annotation_date(annots, "started"),
    )


def normalize_text(text: str) -> str:
    """Return the dedup identity for a task line (case/dash/annotation/signifier-insensitive).

    Strips leading dashes, (Status: date) annotations, checkbox signifiers,
    date tags, priority indicators, and status tags; lowercases; collapses whitespace.

    Args:
        text: A task line to normalize.

    Returns:
        Normalized text ready for deduplication.
    """
    t = _CHECKBOX_RE.sub("", text)
    t = _ANNOT_RE.sub("", t)
    t = _STATUS_TAG_RE.sub("", t)
    t = _DATED_SIGNIFIER_RE.sub("", t)
    t = _PRIORITY_RE.sub("", t)
    _, t = _split_dashes(t.strip())
    return " ".join(t.split()).lower()
