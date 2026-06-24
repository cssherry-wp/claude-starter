from __future__ import annotations

from datetime import datetime

from planner.collectors.gsheet import (
    CompletedItem,
    OpenItem,
    normalize_text,
    parse_completed_line,
    parse_open_line,
)


def test_open_line_counts_carryover_dashes() -> None:
    it = parse_open_line("- - - - - - - Ask for talent review (Waiting: 11/22/2025, 8:26:55 AM)")
    assert it == OpenItem(
        text="Ask for talent review",
        status="Waiting",
        carry_over_weeks=7,
        started_at=None,
    )


def test_open_line_new_item_zero_dashes() -> None:
    it = parse_open_line("Fix budget currency conversion")
    assert it.carry_over_weeks == 0
    assert it.status == ""
    assert it.text == "Fix budget currency conversion"


def test_open_line_multiword_status() -> None:
    it = parse_open_line("- Give feedback (On Notice: 12/15/2025, 6:51:22 PM)")
    assert it.status == "On Notice"
    assert it.carry_over_weeks == 1


def test_open_line_started_captures_date() -> None:
    it = parse_open_line("- Build thing (Started: 1/9/2026, 4:29:26 AM)")
    assert it.status == "Started"
    assert it.started_at == datetime(2026, 1, 9, 4, 29, 26)


def test_open_line_blank_returns_none() -> None:
    assert parse_open_line("   ") is None


def test_completed_line_uses_last_completed_annotation() -> None:
    line = "- Invite to groups (On Notice: 1/5/2026, 4:03:54 AM) (Completed: 1/5/2026, 2:01:52 PM)"
    it = parse_completed_line(line)
    assert it == CompletedItem(
        text="Invite to groups",
        completed_at=datetime(2026, 1, 5, 14, 1, 52),
        started_at=None,
    )


def test_completed_line_with_started_for_duration() -> None:
    line = "- Create feedback (Started: 1/9/2026, 4:29:26 AM) (Completed: 1/9/2026, 4:41:30 AM)"
    it = parse_completed_line(line)
    assert it.started_at == datetime(2026, 1, 9, 4, 29, 26)
    assert it.completed_at == datetime(2026, 1, 9, 4, 41, 30)


def test_completed_line_without_completed_returns_none() -> None:
    assert parse_completed_line("- Some note (Waiting: 1/1/2026, 1:00:00 AM)") is None


def test_normalize_strips_status_dashes_and_signifiers() -> None:
    a = normalize_text("- - Ask for talent review (Waiting: 11/22/2025, 8:26:55 AM)")
    b = normalize_text("- [ ] Ask for talent review ⏫ 📅 2026-06-28 #status/on-notice")
    assert a == b == "ask for talent review"
