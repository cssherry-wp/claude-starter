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


def test_completed_line_blank_returns_none() -> None:
    assert parse_completed_line("   ") is None


def test_open_line_annotation_only_returns_none() -> None:
    assert parse_open_line("- (Waiting: 1/1/2026, 1:00:00 AM)") is None


def test_normalize_strips_status_dashes_and_signifiers() -> None:
    a = normalize_text("- - Ask for talent review (Waiting: 11/22/2025, 8:26:55 AM)")
    b = normalize_text("- [ ] Ask for talent review ⏫ 📅 2026-06-28 #status/on-notice")
    assert a == b == "ask for talent review"


def test_normalize_treats_cancelled_and_in_progress_as_same_task() -> None:
    """A cancelled/in-progress copy must dedup against its open original."""
    base = normalize_text("- [ ] Give feedback #status/waiting")
    cancelled = normalize_text("- [-] Give feedback #status/waiting ❌ 2026-06-24")
    in_progress = normalize_text("- [/] Give feedback #status/waiting")
    assert base == cancelled == in_progress == "give feedback"


def test_normalize_strips_arbitrary_tags() -> None:
    """Provenance/project tags must not affect dedup identity."""
    tagged = normalize_text("- [ ] Give feedback #weekly-planner #project/VIP")
    assert tagged == normalize_text("- [ ] Give feedback") == "give feedback"


class FakeSheets:
    def __init__(self, values: list[list[str]]) -> None:
        self._values = values
        self.requested_range: str | None = None

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, spreadsheetId: str, range: str):  # noqa: N803, A002
        self.requested_range = range
        return self

    def execute(self) -> dict:
        return {"values": self._values}


def _rows() -> list[list[str]]:
    header = ["Week", "% Completed", "# Completed", "Average Time (hrs)",
              "Remaining items", "Notes"]
    week1 = ["1", "20%", "6", "5.1",
             "- - Old task (Waiting: 11/22/2025, 8:26:55 AM)\n- New task",
             "Notes:\n2026/01/05: hi\nCompleted:\n- Done it (Completed: 1/5/2026, 2:01:52 PM)"]
    return [header, week1]


def test_fetch_todos_parses_open_and_completed() -> None:
    from planner.collectors.gsheet import fetch_todos
    result = fetch_todos(FakeSheets(_rows()), "sheet-1", "Overview", 4)
    assert [o.text for o in result["open"]] == ["Old task", "New task"]
    assert [c.text for c in result["completed"]] == ["Done it"]


def test_fetch_todos_locates_columns_by_header_when_reordered() -> None:
    from planner.collectors.gsheet import fetch_todos
    rows = [["Notes", "Week", "Remaining items"],
            ["Completed:\n- D (Completed: 1/5/2026, 2:01:52 PM)", "1", "- Task A"]]
    result = fetch_todos(FakeSheets(rows), "s", "Overview", 4)
    assert [o.text for o in result["open"]] == ["Task A"]
    assert [c.text for c in result["completed"]] == ["D"]


def test_fetch_todos_windows_last_n_plus_one_rows() -> None:
    from planner.collectors.gsheet import fetch_todos
    header = ["Week", "Remaining items", "Notes"]
    data = [[str(i), f"- task{i}", ""] for i in range(1, 11)]
    result = fetch_todos(FakeSheets([header, *data]), "s", "Overview", 2)
    # weeks_back=2 → last 3 rows: task8, task9, task10
    assert [o.text for o in result["open"]] == ["task8", "task9", "task10"]


def test_fetch_todos_empty_sheet() -> None:
    from planner.collectors.gsheet import fetch_todos
    assert fetch_todos(FakeSheets([]), "s") == {"open": [], "completed": []}
