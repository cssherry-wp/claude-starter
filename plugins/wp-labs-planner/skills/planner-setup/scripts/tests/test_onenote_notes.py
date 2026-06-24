from __future__ import annotations

from datetime import date

from planner.onenote_pdf import OneNotePage
from planner.onenote_notes import (
    changes_header, parse_note, render_note, sanitize_filename, versioned_note,
)


def test_sanitize_filename() -> None:
    assert sanitize_filename("VIP: Tesla / Plan?") == "VIP Tesla Plan"


def test_render_note_has_frontmatter_and_body() -> None:
    page = OneNotePage("VIP", "Tesla Plan", date(2026, 5, 26), "body text")
    note = render_note(page, "VIP")
    assert note.startswith("---\n")
    assert "- 2026/05/26" in note
    assert "- project/VIP" in note
    assert "## Notes" in note
    assert note.rstrip().endswith("body text")


def test_render_note_unmapped_has_no_project_tag() -> None:
    page = OneNotePage("WP Labs", "Idea", date(2026, 5, 26), "x")
    assert "project/" not in render_note(page, None)


def test_changes_header_format() -> None:
    assert changes_header(date(2026, 6, 10), date(2026, 6, 3)) == \
        "## Changes - #2026/06/10 from #2026/06/03"


def test_parse_note_roundtrip() -> None:
    page = OneNotePage("VIP", "Tesla Plan", date(2026, 5, 26), "first body")
    note = render_note(page, "VIP")
    d, changes, body = parse_note(note)
    assert d == date(2026, 5, 26)
    assert changes == ""
    assert body.strip() == "first body"


def test_versioned_note_prepends_changes_and_replaces_body() -> None:
    page_v1 = OneNotePage("VIP", "Tesla Plan", date(2026, 5, 26), "old body")
    v1 = render_note(page_v1, "VIP")
    page_v2 = OneNotePage("VIP", "Tesla Plan", date(2026, 6, 10), "new body")
    v2 = versioned_note(v1, page_v2, "VIP", "Added decision X; revised timeline")
    assert "## Changes - #2026/06/10 from #2026/05/26" in v2
    assert "Added decision X" in v2
    assert "## Notes" in v2
    assert v2.rstrip().endswith("new body")    # body replaced with latest
    assert "old body" not in v2                # old body not kept (changelog summarizes)
    d, changes, body = parse_note(v2)
    assert d == date(2026, 6, 10)
    assert "## Changes - #2026/06/10" in changes
    assert body.strip() == "new body"
    # A second version preserves the first changelog entry (newest on top).
    page_v3 = OneNotePage("VIP", "Tesla Plan", date(2026, 6, 20), "newest body")
    v3 = versioned_note(v2, page_v3, "VIP", "Dropped Y")
    assert v3.index("#2026/06/20") < v3.index("#2026/06/10")
    assert "## Changes - #2026/06/10 from #2026/05/26" in v3


def test_parse_note_preserves_body_with_horizontal_rule() -> None:
    page = OneNotePage("VIP", "T", date(2026, 5, 26), "intro\n\n---\n\nafter rule")
    d, changes, body = parse_note(render_note(page, "VIP"))
    assert "intro" in body and "after rule" in body   # body not truncated at the rule


def test_versioned_note_no_old_date_uses_bare_changes_header() -> None:
    existing = "---\ntags:\n- project/VIP\n---\n## Notes\nold\n"   # no date tag
    page = OneNotePage("VIP", "T", date(2026, 6, 10), "new")
    out = versioned_note(existing, page, "VIP", "changed")
    assert "## Changes - #2026/06/10" in out
    assert "## Changes - #2026/06/10 from" not in out   # no 'from' clause when no old date
