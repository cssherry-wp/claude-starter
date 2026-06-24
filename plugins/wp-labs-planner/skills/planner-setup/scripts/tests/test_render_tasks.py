from __future__ import annotations

from datetime import date, datetime

from planner.collectors.gsheet import OpenItem
from planner.render_tasks import (
    TaskRef,
    existing_task_index,
    open_task_line,
    status_slug,
    week_end,
)


def test_week_end_is_sunday() -> None:
    # 2026-06-24 is a Wednesday; that week's Sunday is 2026-06-28
    assert week_end(date(2026, 6, 24)) == date(2026, 6, 28)


def test_status_slug_kebabs_multiword() -> None:
    assert status_slug("On Notice") == "on-notice"


def test_open_task_line_on_notice_high_priority_with_due() -> None:
    item = OpenItem(text="Give feedback", status="On Notice", carry_over_weeks=2, started_at=None)
    line = open_task_line(item, date(2026, 6, 28))
    assert line == "- [ ] Give feedback ⏫ 📅 2026-06-28 #status/on-notice (carried 2w)"


def test_open_task_line_waiting_low_priority() -> None:
    item = OpenItem(text="Ask review", status="Waiting", carry_over_weeks=0, started_at=None)
    line = open_task_line(item, date(2026, 6, 28))
    assert line == "- [ ] Ask review 🔽 #status/waiting"


def test_open_task_line_no_status_plain() -> None:
    item = OpenItem(text="New thing", status="", carry_over_weeks=0, started_at=None)
    assert open_task_line(item, date(2026, 6, 28)) == "- [ ] New thing"


def test_open_task_line_started_shows_start_date() -> None:
    item = OpenItem(text="Build", status="Started", carry_over_weeks=0,
                    started_at=datetime(2026, 1, 9, 4, 0, 0))
    line = open_task_line(item, date(2026, 6, 28))
    assert line == "- [ ] Build 🛫 2026-01-09 #status/started"


class FakeSearchVault:
    def __init__(self, rows: list[dict], fail: bool = False) -> None:
        self._rows = rows
        self._fail = fail

    def search_query(self, query: dict) -> list:
        if self._fail:
            raise RuntimeError("boom")
        return self._rows


def test_existing_task_index_keys_by_normalized_text() -> None:
    rows = [{"text": "Give feedback ⏫ #status/waiting", "path": "d/2026-06-20.md", "completed": False}]
    index = existing_task_index(FakeSearchVault(rows))
    assert "give feedback" in index
    assert index["give feedback"] == TaskRef(path="d/2026-06-20.md",
                                             text="Give feedback ⏫ #status/waiting", completed=False)


def test_existing_task_index_empty_without_search() -> None:
    assert existing_task_index(object()) == {}


def test_existing_task_index_empty_on_query_failure() -> None:
    assert existing_task_index(FakeSearchVault([], fail=True)) == {}
