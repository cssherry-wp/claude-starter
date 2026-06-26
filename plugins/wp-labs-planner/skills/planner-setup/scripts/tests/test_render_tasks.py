from __future__ import annotations

from datetime import date, datetime as _dt
from pathlib import Path

from planner.collectors.gsheet import CompletedItem, OpenItem
from planner.obsidian import FilesystemVault
from planner.render_tasks import (
    TaskRef,
    apply_completed_items,
    apply_llm_tasks,
    apply_open_items,
    existing_task_index,
    open_task_line,
    status_slug,
    week_end,
    week_start,
)


def test_week_end_is_sunday() -> None:
    # 2026-06-24 is a Wednesday; that week's Sunday is 2026-06-28
    assert week_end(date(2026, 6, 24)) == date(2026, 6, 28)


def test_week_start_returns_monday() -> None:
    # 2026-06-24 is a Wednesday.
    assert week_start(date(2026, 6, 24)) == date(2026, 6, 22)
    assert week_end(date(2026, 6, 24)) == date(2026, 6, 28)
    # Monday maps to itself.
    assert week_start(date(2026, 6, 22)) == date(2026, 6, 22)


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
                    started_at=_dt(2026, 1, 9, 4, 0, 0))
    line = open_task_line(item, date(2026, 6, 28))
    assert line == "- [ ] Build 🛫 2026-01-09 #status/started"


def test_open_task_line_in_progress_uses_slash_marker() -> None:
    item = OpenItem(text="Build", status="In Progress", carry_over_weeks=0, started_at=None)
    line = open_task_line(item, date(2026, 6, 28))
    assert line == "- [/] Build #status/in-progress"


def test_open_task_line_cancelled_uses_dash_marker() -> None:
    item = OpenItem(text="Drop it", status="Cancelled", carry_over_weeks=0, started_at=None)
    line = open_task_line(item, date(2026, 6, 28))
    assert line == "- [-] Drop it #status/cancelled"


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


class RecordingVault:
    def __init__(self, files: dict[str, str] | None = None) -> None:
        self.files = files or {}
        self.patches: list[tuple[str, str, str]] = []

    def exists(self, path: str) -> bool:
        return path in self.files

    def write(self, path: str, content: str) -> None:
        self.files[path] = content

    def read(self, path: str) -> str:
        return self.files[path]

    def patch_heading(self, path: str, heading: str, content: str, operation: str = "append") -> None:
        self.patches.append((path, heading, content))


def existing_task_index_stub(key: str, path: str, text: str) -> dict[str, TaskRef]:
    return {key: TaskRef(path=path, text=text, completed=False)}


def test_apply_open_items_appends_new_under_open_items() -> None:
    vault = RecordingVault()
    items = [OpenItem(text="New thing", status="", carry_over_weeks=0, started_at=None)]
    apply_open_items(vault, "daily", items, date(2026, 6, 24), index={})
    assert vault.patches == [("daily/2026-06-24.md", "New open items", "- [ ] New thing #weekly-planner")]
    assert vault.exists("daily/2026-06-24.md")  # stub created


def test_apply_open_items_skips_unchanged_existing() -> None:
    vault = RecordingVault({"daily/2026-06-20.md": "## TODO\n- [ ] New thing\n"})
    items = [OpenItem(text="New thing", status="", carry_over_weeks=0, started_at=None)]
    index = existing_task_index_stub("new thing", "daily/2026-06-20.md", "- [ ] New thing")
    apply_open_items(vault, "daily", items, date(2026, 6, 24), index=index)
    assert vault.patches == []  # nothing new appended
    assert vault.files["daily/2026-06-20.md"] == "## TODO\n- [ ] New thing\n"  # untouched


def test_apply_open_items_supersedes_changed_existing() -> None:
    """A changed task: cancel the old copy ([-]) and resurface the updated one today."""
    vault = RecordingVault({"daily/2026-06-20.md": "## TODO\n- [ ] Give feedback 🔽 #status/waiting\n"})
    items = [OpenItem(text="Give feedback", status="On Notice", carry_over_weeks=1, started_at=None)]
    index = existing_task_index_stub("give feedback", "daily/2026-06-20.md",
                                     "- [ ] Give feedback 🔽 #status/waiting")
    apply_open_items(vault, "daily", items, date(2026, 6, 24), index=index)
    # old copy preserved as a cancelled tombstone (not deleted, not edited in place)
    assert "- [-] Give feedback 🔽 #status/waiting ❌ 2026-06-24" in vault.files["daily/2026-06-20.md"]
    # updated copy resurfaced under today's New open items, stamped with provenance tag
    assert vault.patches == [("daily/2026-06-24.md", "New open items",
                              "- [ ] Give feedback ⏫ 📅 2026-06-28 #status/on-notice (carried 1w) "
                              "#weekly-planner")]


def test_apply_open_items_leaves_already_cancelled_copy() -> None:
    """A matched copy that is already cancelled is left untouched and not resurfaced."""
    vault = RecordingVault(
        {"daily/2026-06-20.md": "## TODO\n- [-] Give feedback 🔽 #status/waiting ❌ 2026-06-19\n"})
    items = [OpenItem(text="Give feedback", status="On Notice", carry_over_weeks=1, started_at=None)]
    index = existing_task_index_stub("give feedback", "daily/2026-06-20.md",
                                     "- [-] Give feedback 🔽 #status/waiting ❌ 2026-06-19")
    apply_open_items(vault, "daily", items, date(2026, 6, 24), index=index)
    assert vault.patches == []
    assert vault.files["daily/2026-06-20.md"] == \
        "## TODO\n- [-] Give feedback 🔽 #status/waiting ❌ 2026-06-19\n"


def test_apply_open_items_does_not_rechurn_untagged_existing() -> None:
    """A pre-existing untagged copy with identical signifiers is left as-is (no migration churn)."""
    vault = RecordingVault({"daily/2026-06-20.md": "## TODO\n- [ ] New thing\n"})
    items = [OpenItem(text="New thing", status="", carry_over_weeks=0, started_at=None)]
    index = existing_task_index_stub("new thing", "daily/2026-06-20.md", "- [ ] New thing")
    apply_open_items(vault, "daily", items, date(2026, 6, 24), index=index)
    assert vault.patches == []
    assert vault.files["daily/2026-06-20.md"] == "## TODO\n- [ ] New thing\n"


def test_apply_llm_tasks_are_not_tagged_as_sheet_sourced() -> None:
    """LLM-synthesized tasks do not get the #weekly-planner provenance tag."""
    vault = RecordingVault()
    apply_llm_tasks(vault, "daily", [{"text": "Deploy service", "priority": "high"}],
                    date(2026, 6, 24), index={}, claimed_keys=set())
    assert "#weekly-planner" not in vault.patches[0][2]


def test_existing_task_index_prefers_live_over_cancelled() -> None:
    rows = [
        {"text": "- [-] Give feedback ❌ 2026-06-01", "path": "d/old.md", "completed": False,
         "status": "-"},
        {"text": "- [ ] Give feedback", "path": "d/new.md", "completed": False, "status": " "},
    ]
    assert existing_task_index(FakeSearchVault(rows))["give feedback"].path == "d/new.md"
    # order-independent: live copy wins regardless of row order
    assert existing_task_index(FakeSearchVault(list(reversed(rows))))["give feedback"].path == "d/new.md"


def test_backfill_creates_completion_note_and_appends_done() -> None:
    vault = RecordingVault()
    items = [CompletedItem(text="Done it", completed_at=_dt(2026, 1, 5, 14, 1, 52), started_at=None)]
    apply_completed_items(vault, "daily", items, index={})
    assert vault.exists("daily/2026-01-05.md")
    assert vault.patches == [("daily/2026-01-05.md", "TODO", "- [x] Done it ✅ 2026-01-05 #weekly-planner")]


def test_backfill_includes_duration_when_started_known() -> None:
    vault = RecordingVault()
    items = [CompletedItem(text="Create feedback",
                           completed_at=_dt(2026, 1, 9, 4, 41, 30),
                           started_at=_dt(2026, 1, 9, 4, 29, 26))]
    apply_completed_items(vault, "daily", items, index={})
    assert vault.patches[0][2] == "- [x] Create feedback ✅ 2026-01-09 (12m) #weekly-planner"


def test_backfill_formats_hours_and_minutes_for_long_duration() -> None:
    vault = RecordingVault()
    items = [CompletedItem(text="Long task",
                           completed_at=_dt(2026, 1, 9, 6, 0, 0),
                           started_at=_dt(2026, 1, 9, 4, 30, 0))]
    apply_completed_items(vault, "daily", items, index={})
    assert vault.patches[0][2] == "- [x] Long task ✅ 2026-01-09 (1h 30m) #weekly-planner"


def test_backfill_skips_already_documented() -> None:
    vault = RecordingVault()
    items = [CompletedItem(text="Done it", completed_at=_dt(2026, 1, 5, 14, 1, 52), started_at=None)]
    index = existing_task_index_stub("done it", "daily/2026-01-05.md", "- [x] Done it ✅ 2026-01-05")
    apply_completed_items(vault, "daily", items, index=index)
    assert vault.patches == []


# --- apply_llm_tasks tests ---

def test_apply_llm_tasks_skips_task_in_index() -> None:
    vault = RecordingVault()
    index = existing_task_index_stub("follow up", "daily/2026-06-23.md", "- [ ] Follow up")
    tasks = [{"text": "Follow up", "priority": "high"}]
    apply_llm_tasks(vault, "daily", tasks, date(2026, 6, 24), index, claimed_keys=set())
    assert vault.patches == []


def test_apply_llm_tasks_skips_task_in_claimed_keys() -> None:
    vault = RecordingVault()
    tasks = [{"text": "Sheet task", "priority": "medium"}]
    apply_llm_tasks(vault, "daily", tasks, date(2026, 6, 24), index={},
                    claimed_keys={"sheet task"})
    assert vault.patches == []


def test_apply_llm_tasks_dedups_identical_within_batch() -> None:
    vault = RecordingVault()
    tasks = [
        {"text": "Write tests", "priority": "high"},
        {"text": "Write tests", "priority": "low"},
    ]
    apply_llm_tasks(vault, "daily", tasks, date(2026, 6, 24), index={}, claimed_keys=set())
    assert len(vault.patches) == 1
    assert "Write tests" in vault.patches[0][2]


def test_apply_llm_tasks_renders_survivor_with_priority_emoji() -> None:
    vault = RecordingVault()
    tasks = [{"text": "Deploy service", "priority": "high"}]
    apply_llm_tasks(vault, "daily", tasks, date(2026, 6, 24), index={}, claimed_keys=set())
    assert vault.patches == [("daily/2026-06-24.md", "New open items", "- [ ] Deploy service ⏫")]


def test_apply_llm_tasks_no_patch_when_all_duplicates() -> None:
    vault = RecordingVault()
    index = existing_task_index_stub("existing task", "daily/2026-06-20.md", "- [ ] Existing task")
    tasks = [{"text": "Existing task", "priority": "medium"}]
    apply_llm_tasks(vault, "daily", tasks, date(2026, 6, 24), index=index, claimed_keys=set())
    assert vault.patches == []


def test_apply_llm_tasks_no_patch_for_empty_text() -> None:
    vault = RecordingVault()
    tasks = [{"text": "", "priority": "high"}, {"text": "  ", "priority": "low"}]
    apply_llm_tasks(vault, "daily", tasks, date(2026, 6, 24), index={}, claimed_keys=set())
    assert vault.patches == []


# --- self-healing when the daily note lacks the target heading (real-backend repro) ---

def test_apply_llm_tasks_adds_open_items_heading_when_template_omits_it(tmp_path: Path) -> None:
    """A daily note from a template without '## New open items' must not break the patch."""
    (tmp_path / "daily").mkdir()
    note = tmp_path / "daily" / "2026-06-24.md"
    note.write_text("## Notes\n\n## TODO\n")  # daily-notes template lacks New open items
    vault = FilesystemVault(str(tmp_path))
    tasks = [{"text": "Deploy service", "priority": "high"}]
    apply_llm_tasks(vault, "daily", tasks, date(2026, 6, 24), index={}, claimed_keys=set())
    body = note.read_text()
    assert "## New open items" in body
    assert "- [ ] Deploy service ⏫" in body


def test_apply_open_items_adds_open_items_heading_when_template_omits_it(tmp_path: Path) -> None:
    """apply_open_items self-heals a missing '## New open items' heading on an existing note."""
    (tmp_path / "daily").mkdir()
    note = tmp_path / "daily" / "2026-06-24.md"
    note.write_text("## Notes\n\n## TODO\n")
    vault = FilesystemVault(str(tmp_path))
    items = [OpenItem(text="New thing", status="", carry_over_weeks=0, started_at=None)]
    apply_open_items(vault, "daily", items, date(2026, 6, 24), index={})
    body = note.read_text()
    assert "## New open items" in body
    assert "- [ ] New thing" in body
