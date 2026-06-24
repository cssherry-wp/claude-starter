"""Render imported OneNote pages to notes and assemble versioned (changelog) notes."""
from __future__ import annotations

import re
from datetime import date

from planner.onenote_pdf import OneNotePage

_BODY_HEADING = "## Notes"
_DATE_TAG = re.compile(r"^- (\d{4}/\d{2}/\d{2})$", re.MULTILINE)


def sanitize_filename(title: str) -> str:
    """Make a filesystem-safe note basename from a page title (no extension).

    Args:
        title: The page title to sanitize.

    Returns:
        A filesystem-safe basename, or "Untitled" if empty after sanitization.
    """
    cleaned = re.sub(r'[\\/:*?"<>|#^\[\]]', " ", title)
    return re.sub(r"\s+", " ", cleaned).strip() or "Untitled"


def changes_header(new: date, old: date) -> str:
    """Return the versioning header line for a re-import diff.

    Args:
        new: The new (current) date.
        old: The old (previous) date.

    Returns:
        A formatted changes header string.
    """
    return f"## Changes - #{new:%Y/%m/%d} from #{old:%Y/%m/%d}"


def _frontmatter(d: date | None, project: str | None) -> str:
    """Generate frontmatter with tags for date and project.

    Args:
        d: The date to include, or None.
        project: The project name to include, or None.

    Returns:
        The frontmatter block as a string.
    """
    tags = []
    if d:
        tags.append(f"- {d:%Y/%m/%d}")
    if project:
        tags.append(f"- project/{project}")
    return "---\ntags:\n" + "\n".join(tags) + "\n---\n"


def render_note(page: OneNotePage, project: str | None) -> str:
    """Render a fresh note: frontmatter + a '## Notes' body section.

    Args:
        page: The OneNotePage to render.
        project: The project name to tag, or None.

    Returns:
        The rendered note as a string.
    """
    return _frontmatter(page.date, project) + f"{_BODY_HEADING}\n{page.body}\n"


def parse_note(text: str) -> tuple[date | None, str, str]:
    """Split a note into (stored_date, changes-blocks text, body text).

    Args:
        text: The note text to parse.

    Returns:
        A tuple of (stored_date, changes_blocks, body).
        stored_date is None if no date found in frontmatter.
        changes_blocks is the text between frontmatter and ## Notes.
        body is the text after ## Notes.
    """
    parts = re.split(r"(?m)^---\s*$", text, maxsplit=2)
    frontmatter, after_fm = (parts[1], parts[2]) if len(parts) >= 3 else ("", text)
    stored: date | None = None
    m = _DATE_TAG.search(frontmatter)
    if m:
        y, mo, d = (int(x) for x in m.group(1).split("/"))
        stored = date(y, mo, d)
    body_parts = re.split(r"(?m)^## Notes\s*$", after_fm, maxsplit=1)
    if len(body_parts) >= 2:
        return stored, body_parts[0].strip(), body_parts[1].strip()
    return stored, "", after_fm.strip()


def versioned_note(
    existing: str, page: OneNotePage, project: str | None, summary: str
) -> str:
    """Prepend a dated changes block, keep prior changes, replace body with latest.

    Args:
        existing: The existing note text.
        page: The new OneNotePage to incorporate.
        project: The project name to tag, or None.
        summary: A summary of the changes made.

    Returns:
        The versioned note with new changes prepended and body replaced.
    """
    old_date, old_changes, _ = parse_note(existing)
    header = changes_header(page.date, old_date) if (page.date and old_date) else \
        f"## Changes - #{page.date:%Y/%m/%d}"
    block = f"{header}\n{summary.strip()}\n"
    prior = (old_changes + "\n") if old_changes else ""
    return (_frontmatter(page.date, project) + block + "\n" + prior
            + f"{_BODY_HEADING}\n{page.body}\n")
