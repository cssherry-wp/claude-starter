# Google Sheets Todo Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the daily planner's Google Doc todo collector with a Google Sheets collector that parses the `Overview` tab into deduped, priority-tagged Obsidian Tasks and backfills completed items into their completion-date notes.

**Architecture:** A new `collectors/gsheet.py` reads the tab via the Sheets API and parses its cells (regex, deterministic — no LLM) into structured open/completed items. A new `render_tasks.py` renders Obsidian Tasks-syntax lines, dedups/reconciles against existing vault tasks via a Dataview query (`vault.search_query`), and backfills completed items. `daily.py` wires the collector in and calls the new render step after the existing LLM synthesis (which is unchanged).

**Tech Stack:** Python 3.11, `google-api-python-client` (already a dep), stdlib `re`/`datetime`, `pytest`. No new dependencies.

## Global Constraints

- Python ≥ 3.11; manage env with `uv`; run tests with `uv run pytest` from `plugins/wp-labs-planner/skills/planner-setup/scripts`.
- Lint/type: `ruff` + `mypy` clean. Type-annotate all new function signatures and class attributes. Google-style docstrings on public functions.
- Hand-written functions < 40 lines; extract helpers otherwise.
- No new third-party dependencies ("a little copying over a little dependency").
- Read-only access to the Sheet; never write back to Google.
- Tests mirror module structure (`planner/foo.py` → `tests/test_foo.py`); cover happy path, edge cases, invalid input. No live network/Sheets/MCP in unit tests — use fakes.
- Carry-over weeks = leading dash count (0 dashes = new this week). End of week = **Sunday** (`week_start + 6`, week_start = Monday). Status may be multi-word (e.g. `On Notice`). Status carried as `#status/<slug>` tag, excluded from the dedup identity.
- Date grammar in the Sheet: `M/D/YYYY, H:MM:SS AM/PM` (`%m/%d/%Y, %I:%M:%S %p`).
- All paths below are relative to `plugins/wp-labs-planner/skills/planner-setup/scripts`.

---

### Task 1: Config — Sheets ID + tab/weeks settings

**Files:**
- Modify: `planner/config.py` (`_DOC_ID_RE`/`extract_doc_id` :14,80-84; `GoogleCfg` :17-22; `_build_google` :86-93)
- Modify: `templates/config.example.yaml`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `GoogleCfg` gains `overview_tab: str` and `weeks_back: int`. `extract_doc_id(value: str) -> str` now also extracts the ID from `/spreadsheets/d/<id>` URLs.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_config.py`:

```python
from planner.config import extract_doc_id


def test_extract_doc_id_handles_spreadsheet_url() -> None:
    url = "https://docs.google.com/spreadsheets/d/1bB8LVB_Y5AZ/edit?gid=23#gid=23"
    assert extract_doc_id(url) == "1bB8LVB_Y5AZ"


def test_extract_doc_id_passes_bare_id() -> None:
    assert extract_doc_id("1bB8LVB_Y5AZ") == "1bB8LVB_Y5AZ"


def test_google_cfg_tab_and_weeks_defaults(tmp_path) -> None:
    from planner.config import load_config
    cfg_file = tmp_path / "c.yaml"
    cfg_file.write_text(
        "google:\n"
        "  credentials_path: /c.json\n  token_path: /t.json\n"
        "  planner_address: a@b.com\n  gdoc_id: SHEET123\n"
        "vault:\n  path: " + str(tmp_path) + "\n"
    )
    cfg = load_config(str(cfg_file))
    assert cfg.google.overview_tab == "Overview"
    assert cfg.google.weeks_back == 4
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `uv run pytest tests/test_config.py -k "spreadsheet or tab_and_weeks" -v`
Expected: FAIL (`overview_tab` attribute missing; spreadsheet URL returns the full string).

- [ ] **Step 3: Implement**

In `planner/config.py`, widen the regex (line 14) to match both URL shapes:

```python
_DOC_ID_RE = re.compile(r"/(?:document|spreadsheets)/d/([A-Za-z0-9_-]+)")
```

Add fields to `GoogleCfg` (after line 22, `gdoc_id: str`):

```python
    overview_tab: str = "Overview"
    weeks_back: int = 4
```

Set them in `_build_google` (inside the `GoogleCfg(...)` call, after `gdoc_id=...`):

```python
        overview_tab=g.get("overview_tab", "Overview"),
        weeks_back=int(g.get("weeks_back", 4)),
```

- [ ] **Step 4: Update the config template**

In `templates/config.example.yaml`, under the `google:` section change the `gdoc_id` comment and add the two keys:

```yaml
  # Google Sheet that holds your todos (Overview tab). Full URL or bare ID.
  gdoc_id: 1AbCdEfGhIjKlMnOpQrStUvWxYz
  # Worksheet/tab name to read, and how many prior weeks (rows) to scan.
  overview_tab: Overview
  weeks_back: 4
```

- [ ] **Step 5: Run tests, verify pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add planner/config.py templates/config.example.yaml tests/test_config.py
git commit -m "feat(planner): config supports Sheets id, overview_tab, weeks_back"
```

---

### Task 2: Gmail collector — Sheets scope + client

**Files:**
- Modify: `planner/collectors/gmail.py` (`GMAIL_SCOPES` :17-18; `build_docs` :76-78)
- Test: `tests/test_collectors_gmail.py`

**Interfaces:**
- Produces: `build_sheets(creds) -> Any` (Sheets v4 client). `GMAIL_SCOPES` now requests `spreadsheets.readonly` instead of `documents.readonly`. `build_docs` is removed.

- [ ] **Step 1: Write failing test**

Add to `tests/test_collectors_gmail.py`:

```python
def test_gmail_scopes_use_spreadsheets() -> None:
    from planner.collectors.gmail import GMAIL_SCOPES
    assert any("spreadsheets.readonly" in s for s in GMAIL_SCOPES)
    assert not any("documents.readonly" in s for s in GMAIL_SCOPES)


def test_build_sheets_exists() -> None:
    from planner.collectors import gmail
    assert callable(gmail.build_sheets)
```

- [ ] **Step 2: Run test, verify it fails**

Run: `uv run pytest tests/test_collectors_gmail.py -k "scopes or build_sheets" -v`
Expected: FAIL (`build_sheets` missing; scope still `documents.readonly`).

- [ ] **Step 3: Implement**

In `planner/collectors/gmail.py`, change `GMAIL_SCOPES` (lines 17-18):

```python
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/spreadsheets.readonly"]
```

Replace `build_docs` (lines 76-78) with:

```python
def build_sheets(creds: Credentials) -> Any:
    """Build the Google Sheets API client."""
    return build("sheets", "v4", credentials=creds, cache_discovery=False)
```

- [ ] **Step 4: Run test, verify pass**

Run: `uv run pytest tests/test_collectors_gmail.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add planner/collectors/gmail.py tests/test_collectors_gmail.py
git commit -m "feat(planner): Sheets OAuth scope + build_sheets client"
```

---

### Task 3: gsheet parser — line grammar (open + completed)

**Files:**
- Create: `planner/collectors/gsheet.py`
- Test: `tests/test_collectors_gsheet.py`

**Interfaces:**
- Produces:
  - `@dataclass OpenItem(text: str, status: str, carry_over_weeks: int, started_at: datetime | None)`
  - `@dataclass CompletedItem(text: str, completed_at: datetime, started_at: datetime | None)`
  - `parse_open_line(line: str) -> OpenItem | None`
  - `parse_completed_line(line: str) -> CompletedItem | None`
  - `normalize_text(text: str) -> str` (dedup identity: strips leading dashes, `(<Status>: <date>)` annotations, Tasks signifiers/dates, `#status/*` tags; lowercases; collapses whitespace)

- [ ] **Step 1: Write failing tests**

Create `tests/test_collectors_gsheet.py`:

```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `uv run pytest tests/test_collectors_gsheet.py -v`
Expected: FAIL (`No module named 'planner.collectors.gsheet'`).

- [ ] **Step 3: Implement the grammar**

Create `planner/collectors/gsheet.py`:

```python
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
    text: str
    status: str
    carry_over_weeks: int
    started_at: datetime | None


@dataclass
class CompletedItem:
    text: str
    completed_at: datetime
    started_at: datetime | None


def _parse_dt(raw: str) -> datetime | None:
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
    return line[: m.end()].count("-"), line[m.end():]


def _annotation_date(annots: list[tuple[str, datetime | None]], word: str) -> datetime | None:
    return next((dt for w, dt in annots if w.lower() == word and dt), None)


def parse_open_line(line: str) -> OpenItem | None:
    """Parse one 'Remaining items' line into an OpenItem, or None if blank/unparseable."""
    stripped = line.strip()
    if not stripped:
        return None
    dashes, body = _split_dashes(stripped)
    annots = _annotations(body)
    text = _ANNOT_RE.sub("", body).strip()
    if not text:
        return None
    status = annots[-1][0] if annots else ""
    return OpenItem(text=text, status=status, carry_over_weeks=dashes,
                    started_at=_annotation_date(annots, "started"))


def parse_completed_line(line: str) -> CompletedItem | None:
    """Parse one 'Completed:' line into a CompletedItem, or None if no completion date."""
    stripped = line.strip()
    if not stripped:
        return None
    _, body = _split_dashes(stripped)
    annots = _annotations(body)
    text = _ANNOT_RE.sub("", body).strip()
    completed = next((dt for w, dt in reversed(annots) if w.lower() == "completed" and dt), None)
    if not text or completed is None:
        return None
    return CompletedItem(text=text, completed_at=completed,
                         started_at=_annotation_date(annots, "started"))


def normalize_text(text: str) -> str:
    """Return the dedup identity for a task line (case/dash/annotation/signifier-insensitive)."""
    t = _CHECKBOX_RE.sub("", text)
    t = _ANNOT_RE.sub("", t)
    t = _STATUS_TAG_RE.sub("", t)
    t = _DATED_SIGNIFIER_RE.sub("", t)
    t = _PRIORITY_RE.sub("", t)
    _, t = _split_dashes(t.strip())
    return " ".join(t.split()).lower()
```

- [ ] **Step 4: Run tests, verify pass**

Run: `uv run pytest tests/test_collectors_gsheet.py -v`
Expected: PASS (all 9 tests).

- [ ] **Step 5: Commit**

```bash
git add planner/collectors/gsheet.py tests/test_collectors_gsheet.py
git commit -m "feat(planner): gsheet line grammar for open/completed todos"
```

---

### Task 4: gsheet `fetch_todos` — read tab, locate columns, window rows

**Files:**
- Modify: `planner/collectors/gsheet.py`
- Test: `tests/test_collectors_gsheet.py`

**Interfaces:**
- Consumes: `parse_open_line`, `parse_completed_line` (Task 3).
- Produces: `fetch_todos(sheets_service: Any, sheet_id: str, tab: str = "Overview", weeks_back: int = 4) -> dict[str, list]` returning `{"open": [OpenItem...], "completed": [CompletedItem...]}`.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_collectors_gsheet.py`:

```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `uv run pytest tests/test_collectors_gsheet.py -k fetch_todos -v`
Expected: FAIL (`fetch_todos` not defined).

- [ ] **Step 3: Implement**

Append to `planner/collectors/gsheet.py`:

```python
from typing import Any


def _completed_section(notes: str) -> list[str]:
    """Return lines after a 'Completed:' marker inside the Notes cell."""
    out: list[str] = []
    capturing = False
    for line in notes.splitlines():
        if line.strip().lower().rstrip(":") == "completed":
            capturing = True
            continue
        if capturing:
            out.append(line)
    return out


def _column(header: list[str], name: str) -> int:
    lowered = [h.strip().lower() for h in header]
    return lowered.index(name) if name in lowered else -1


def _cell(row: list[str], idx: int) -> str:
    return row[idx] if 0 <= idx < len(row) else ""


def fetch_todos(sheets_service: Any, sheet_id: str, tab: str = "Overview",
                weeks_back: int = 4) -> dict[str, list]:
    """Read the Overview tab and parse recent rows into open/completed todos.

    Args:
        sheets_service: Google Sheets v4 API client.
        sheet_id: Spreadsheet ID.
        tab: Worksheet/tab name to read.
        weeks_back: Number of prior week-rows to include alongside the current row.

    Returns:
        Dict with "open" (list[OpenItem]) and "completed" (list[CompletedItem]).
    """
    resp = sheets_service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=tab).execute()
    rows = resp.get("values", [])
    if not rows:
        return {"open": [], "completed": []}
    header, body = rows[0], rows[1:]
    rem_i, notes_i = _column(header, "remaining items"), _column(header, "notes")
    populated = [r for r in body if any(c.strip() for c in r)]
    open_items: list[OpenItem] = []
    completed: list[CompletedItem] = []
    for row in populated[-(weeks_back + 1):]:
        for line in _cell(row, rem_i).splitlines():
            item = parse_open_line(line)
            if item:
                open_items.append(item)
            elif line.strip():
                log.warning("unparsed open line: %r", line)
        for line in _completed_section(_cell(row, notes_i)):
            done = parse_completed_line(line)
            if done:
                completed.append(done)
    return {"open": open_items, "completed": completed}
```

(Move the `from typing import Any` import to the top of the file with the other imports to satisfy ruff.)

- [ ] **Step 4: Run tests, verify pass**

Run: `uv run pytest tests/test_collectors_gsheet.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add planner/collectors/gsheet.py tests/test_collectors_gsheet.py
git commit -m "feat(planner): gsheet fetch_todos reads tab, columns, row window"
```

---

### Task 5: Render tasks — line builder + Dataview task index

**Files:**
- Create: `planner/render_tasks.py`
- Test: `tests/test_render_tasks.py`

**Interfaces:**
- Consumes: `OpenItem`, `CompletedItem`, `normalize_text` (Tasks 3-4); `priority_emoji` from `planner.errors`.
- Produces:
  - `week_end(today: date) -> date` (the Sunday of `today`'s week)
  - `status_slug(status: str) -> str`
  - `open_task_line(item: OpenItem, end: date) -> str`
  - `@dataclass TaskRef(path: str, text: str, completed: bool)`
  - `existing_task_index(vault) -> dict[str, TaskRef]` (keyed by `normalize_text`; `{}` if the vault has no `search_query` or the query fails)

- [ ] **Step 1: Write failing tests**

Create `tests/test_render_tasks.py`:

```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `uv run pytest tests/test_render_tasks.py -v`
Expected: FAIL (`No module named 'planner.render_tasks'`).

- [ ] **Step 3: Implement**

Create `planner/render_tasks.py`:

```python
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
```

- [ ] **Step 4: Run tests, verify pass**

Run: `uv run pytest tests/test_render_tasks.py -v`
Expected: PASS.

> Note: the `{"queryType": "dataview", "dql": ...}` argument shape and the Dataview row keys (`text`/`path`/`completed`) are the obsidian-mcp `search_query` contract, which is exercised live for the first time here. The dedup *logic* is fully unit-tested against fakes; the real query/row shape is verified in Task 8's manual run, and only `_TASK_DQL` / `_row_value` keys would need adjustment if the live server differs.

- [ ] **Step 5: Commit**

```bash
git add planner/render_tasks.py tests/test_render_tasks.py
git commit -m "feat(planner): open-task line builder + Dataview task index"
```

---

### Task 6: Apply open items — render new + reconcile existing

**Files:**
- Modify: `planner/render_tasks.py`
- Test: `tests/test_render_tasks.py`

**Interfaces:**
- Consumes: `open_task_line`, `existing_task_index`, `TaskRef`, `normalize_text`; vault methods `exists`, `write`, `read`, `patch_heading` (see `planner/obsidian.py` Protocol).
- Produces: `apply_open_items(vault, daily_dir: str, items: list[OpenItem], today: date, index: dict[str, TaskRef]) -> None` — appends new items under `## Open Items` in today's note; reconciles priority/due/status on existing matches in place.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_render_tasks.py`:

```python
from planner.render_tasks import apply_open_items


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


def test_apply_open_items_appends_new_under_open_items() -> None:
    vault = RecordingVault()
    items = [OpenItem(text="New thing", status="", carry_over_weeks=0, started_at=None)]
    apply_open_items(vault, "daily", items, date(2026, 6, 24), index={})
    assert vault.patches == [("daily/2026-06-24.md", "Open Items", "- [ ] New thing")]
    assert vault.exists("daily/2026-06-24.md")  # stub created


def test_apply_open_items_skips_unchanged_existing() -> None:
    vault = RecordingVault({"daily/2026-06-20.md": "## TODO\n- [ ] New thing\n"})
    items = [OpenItem(text="New thing", status="", carry_over_weeks=0, started_at=None)]
    index = existing_task_index_stub("new thing", "daily/2026-06-20.md", "- [ ] New thing")
    apply_open_items(vault, "daily", items, date(2026, 6, 24), index=index)
    assert vault.patches == []  # nothing new appended
    assert vault.files["daily/2026-06-20.md"] == "## TODO\n- [ ] New thing\n"  # untouched


def test_apply_open_items_reconciles_stale_priority() -> None:
    vault = RecordingVault({"daily/2026-06-20.md": "## TODO\n- [ ] Give feedback 🔽 #status/waiting\n"})
    items = [OpenItem(text="Give feedback", status="On Notice", carry_over_weeks=1, started_at=None)]
    index = existing_task_index_stub("give feedback", "daily/2026-06-20.md",
                                     "- [ ] Give feedback 🔽 #status/waiting")
    apply_open_items(vault, "daily", items, date(2026, 6, 24), index=index)
    assert vault.patches == []  # already exists → not re-appended
    assert "⏫ 📅 2026-06-28 #status/on-notice" in vault.files["daily/2026-06-20.md"]
    assert "🔽 #status/waiting" not in vault.files["daily/2026-06-20.md"]


def existing_task_index_stub(key: str, path: str, text: str):
    return {key: TaskRef(path=path, text=text, completed=False)}
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `uv run pytest tests/test_render_tasks.py -k apply_open -v`
Expected: FAIL (`apply_open_items` not defined).

- [ ] **Step 3: Implement**

Append to `planner/render_tasks.py`:

```python
_OPEN_HEADING = "Open Items"
_STUB = "## Notes\n\n## TODO\n"


def _ensure_note(vault: Any, path: str) -> None:
    if not vault.exists(path):
        vault.write(path, _STUB)


def _reconcile(vault: Any, ref: TaskRef, item: OpenItem, end: date) -> None:
    """Rewrite the matched task line's signifiers in place, preserving checkbox state."""
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
    """Append new open items under today's '## Open Items'; reconcile existing matches."""
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
        _ensure_note(vault, today_path)
        vault.patch_heading(today_path, _OPEN_HEADING, "\n".join(new_lines), operation="append")
```

> The `## Open Items` heading must exist in the daily note for `patch_heading` to target it. The Daily template adds it in Task 8; for notes created as a stub here, add the heading to `_STUB`:
> change `_STUB = "## Notes\n\n## TODO\n"` to `_STUB = "## Notes\n\n## Open Items\n\n## TODO\n"`.

- [ ] **Step 4: Run tests, verify pass**

Run: `uv run pytest tests/test_render_tasks.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add planner/render_tasks.py tests/test_render_tasks.py
git commit -m "feat(planner): apply open items — append new, reconcile existing"
```

---

### Task 7: Backfill completed items into completion-date notes

**Files:**
- Modify: `planner/render_tasks.py`
- Test: `tests/test_render_tasks.py`

**Interfaces:**
- Consumes: `CompletedItem`, `normalize_text`, `TaskRef`, `_ensure_note`; vault `exists`/`write`/`patch_heading`.
- Produces: `apply_completed_items(vault, daily_dir: str, items: list[CompletedItem], index: dict[str, TaskRef]) -> None` — for each undocumented completed item, ensures the completion-date note exists and appends `- [x] <text> ✅ <date>[ (duration)]` under its `## TODO`.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_render_tasks.py`:

```python
from datetime import datetime as _dt

from planner.collectors.gsheet import CompletedItem
from planner.render_tasks import apply_completed_items


def test_backfill_creates_completion_note_and_appends_done() -> None:
    vault = RecordingVault()
    items = [CompletedItem(text="Done it", completed_at=_dt(2026, 1, 5, 14, 1, 52), started_at=None)]
    apply_completed_items(vault, "daily", items, index={})
    assert vault.exists("daily/2026-01-05.md")
    assert vault.patches == [("daily/2026-01-05.md", "TODO", "- [x] Done it ✅ 2026-01-05")]


def test_backfill_includes_duration_when_started_known() -> None:
    vault = RecordingVault()
    items = [CompletedItem(text="Create feedback",
                           completed_at=_dt(2026, 1, 9, 4, 41, 30),
                           started_at=_dt(2026, 1, 9, 4, 29, 26))]
    apply_completed_items(vault, "daily", items, index={})
    assert vault.patches[0][2] == "- [x] Create feedback ✅ 2026-01-09 (12m)"


def test_backfill_skips_already_documented() -> None:
    vault = RecordingVault()
    items = [CompletedItem(text="Done it", completed_at=_dt(2026, 1, 5, 14, 1, 52), started_at=None)]
    index = existing_task_index_stub("done it", "daily/2026-01-05.md", "- [x] Done it ✅ 2026-01-05")
    apply_completed_items(vault, "daily", items, index=index)
    assert vault.patches == []
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `uv run pytest tests/test_render_tasks.py -k backfill -v`
Expected: FAIL (`apply_completed_items` not defined).

- [ ] **Step 3: Implement**

Append to `planner/render_tasks.py`:

```python
def _duration_suffix(item: CompletedItem) -> str:
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
    """Backfill undocumented completed items into their completion-date daily notes."""
    for item in items:
        if normalize_text(item.text) in index:
            continue
        day = item.completed_at.date()
        path = f"{daily_dir}/{day.isoformat()}.md"
        _ensure_note(vault, path)
        line = f"- [x] {item.text} ✅ {day.isoformat()}{_duration_suffix(item)}"
        vault.patch_heading(path, "TODO", line, operation="append")
```

Add `CompletedItem` to the import from `planner.collectors.gsheet` at the top of `render_tasks.py`:

```python
from planner.collectors.gsheet import CompletedItem, OpenItem, normalize_text
```

- [ ] **Step 4: Run tests, verify pass**

Run: `uv run pytest tests/test_render_tasks.py -v`
Expected: PASS (all render_tasks tests).

- [ ] **Step 5: Commit**

```bash
git add planner/render_tasks.py tests/test_render_tasks.py
git commit -m "feat(planner): backfill completed items into completion-date notes"
```

---

### Task 8: Wire into daily run; remove gdoc; update template & docs

**Files:**
- Modify: `planner/daily.py` (imports :10; `services` :37-41; `_gather_daily` :44-54; `run_daily` :67-74)
- Delete: `planner/collectors/gdoc.py`, `tests/test_collectors_gdoc.py`
- Modify: `templates/Daily.md` (add `## Open Items` heading)
- Modify: `plugins/wp-labs-planner/README.md` (Importing section / collector description), `~/Notes/config.yaml` note (manual)
- Test: `tests/test_smoke.py`, `tests/test_entrypoints.py`

**Interfaces:**
- Consumes: `gsheet.fetch_todos` (Task 4), `gmail.build_sheets` (Task 2), `render_tasks.apply_open_items` / `apply_completed_items` / `existing_task_index` (Tasks 5-7).

- [ ] **Step 1: Write the failing wiring test**

Add to `tests/test_smoke.py` (or `tests/test_entrypoints.py` if smoke imports differ):

```python
def test_daily_module_uses_gsheet_not_gdoc() -> None:
    import planner.daily as daily
    src = __import__("inspect").getsource(daily)
    assert "gsheet" in src
    assert "gdoc" not in src


def test_gdoc_module_removed() -> None:
    import importlib
    try:
        importlib.import_module("planner.collectors.gdoc")
    except ModuleNotFoundError:
        return
    raise AssertionError("planner.collectors.gdoc should be removed")
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `uv run pytest tests/test_smoke.py -k "gsheet or gdoc_module" -v`
Expected: FAIL (daily still imports `gdoc`; module still present).

- [ ] **Step 3: Rewire `daily.py`**

Change the collectors import (line 10):

```python
from planner.collectors import gmail, gsheet, onenote
```

In `services()` (lines 37-41), swap the Docs client for Sheets:

```python
    def services() -> tuple:  # lazy: only authenticate if a Google collector runs
        if "g" not in creds_holder:
            creds = gmail.get_credentials(cfg.google, gmail.GMAIL_SCOPES)
            creds_holder["g"] = (gmail.build_gmail(creds), gmail.build_sheets(creds))
        return creds_holder["g"]
```

In `_gather_daily` (lines 44-54), replace the `"todos"` entry with a structured `"sheet"` entry (failure degrades to an empty result, not the string sentinel `_safe` returns):

```python
    def sheet_todos() -> dict:
        try:
            return gsheet.fetch_todos(services()[1], cfg.google.gdoc_id,
                                      cfg.google.overview_tab, cfg.google.weeks_back)
        except Exception as exc:  # noqa: BLE001 — degrade, never abort
            log.warning("daily collector 'gsheet' failed: %s", exc)
            return {"open": [], "completed": []}

    return {
        "accomplishments": _safe("gmail", lambda: gmail.fetch_accomplishments(
            services()[0], cfg.google.planner_address, week_start)),
        "calls": _safe("calls", lambda: [e.__dict__ for e in gmail.fetch_calls(
            services()[0], cfg.google.planner_address)]),
        "sheet": sheet_todos(),
        "onenote": _safe("onenote", lambda: "\n\n".join(
            onenote.convert(p, cfg.onenote.converter_command) for p in cfg.onenote.files)),
        "recent_notes": _safe("recent", lambda: [n.__dict__ for n in recent_notes(
            vault, cfg, today, repo)]),
    }
```

Update the daily-synthesis prompt's payload note: in `templates/prompts/daily_synthesis.md`, drop "Google Doc todos" wording and the `new_tasks` array is no longer the task source — leave the LLM shape unchanged (tasks now come from the Sheet), but remove `todos` from the payload (done above) so the model isn't told to invent tasks. (No code change beyond the payload key removal.)

In `run_daily` (after `render_daily`, line 70), apply the Sheet-derived tasks:

```python
    path = render_daily(vault, cfg, synthesis, today)
    sheet = payload.get("sheet", {"open": [], "completed": []})
    index = render_tasks.existing_task_index(vault)
    render_tasks.apply_open_items(vault, cfg.vault.daily_output_dir,
                                  sheet["open"], today, index)
    render_tasks.apply_completed_items(vault, cfg.vault.daily_output_dir,
                                       sheet["completed"], index)
```

Add the import near the top of `daily.py`:

```python
from planner import render_tasks
```

- [ ] **Step 4: Remove the gdoc collector and its test**

```bash
git rm planner/collectors/gdoc.py tests/test_collectors_gdoc.py
```

- [ ] **Step 5: Add the `## Open Items` heading to the Daily template**

In `templates/Daily.md`, add the heading between `## Notes` and `## TODO` (around line 16):

```markdown
## Notes


## Open Items


## TODO
```

- [ ] **Step 6: Run the full suite + lint + types**

Run: `uv run pytest -q && uv run ruff check . && uv run mypy planner`
Expected: all tests PASS; ruff and mypy clean.

- [ ] **Step 7: Manual integration run (validates the Dataview contract)**

With Obsidian open + `OBSIDIAN_API_KEY` set, and `~/Notes/config.yaml` `gdoc_id` pointing at the real Sheet:

```bash
source ~/.zshrc
uv run python -m planner.daily --config ~/Notes/config.yaml
```

Verify in the vault:
- Today's note has open items under `## Open Items` with correct priority/`📅`/`#status/*`.
- A completed item's `- [x] … ✅ <date>` landed in that date's note.
- Re-running does **not** duplicate tasks (dedup works) and updates a changed status in place (reconcile works).

If the run logs a Dataview/`search_query` error, adjust `_TASK_DQL` / `_row_value` keys in `render_tasks.py` to match the live obsidian-mcp `search_query` response, then re-run.

- [ ] **Step 8: Update docs**

In `plugins/wp-labs-planner/README.md`, change the collector description from "a Google Doc" to "a Google Sheet (`Overview` tab)" and note the `spreadsheets.readonly` scope + Sheets API enablement. Update `~/Notes/README.md` step 1 (the OAuth scope is now Sheets, and `gdoc_id` holds a Sheet URL).

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(planner): wire gsheet collector into daily; drop gdoc"
```

---

## Self-Review

**Spec coverage:**
- Replace Docs collector with Sheets reading the `Overview` tab → Tasks 2, 4, 8. ✓
- Parse open items into `- [ ]` with status-derived priority → Tasks 3, 5, 6. ✓
- Detect completed-but-undocumented items, backfill into completion-date note as `- [x] … ✅` → Task 7. ✓
- Dedup + reconcile via Dataview → Tasks 5, 6 (reconcile), 7 (skip). ✓
- Resilient (`_safe`/degrade) → Task 8 `sheet_todos` wrapper; `existing_task_index` degrades. ✓
- Config keys (`overview_tab`, `weeks_back`), `extract_doc_id` for spreadsheets → Task 1. ✓
- Scope change `documents.readonly` → `spreadsheets.readonly` → Task 2, manual re-auth in Task 8. ✓
- 0 dashes = new; end of week = Sunday; multi-word status; `#status/<slug>` tag → Tasks 3, 5 (tested). ✓
- Normalization strips status suffix from open + completed lines → Task 3 (`test_normalize_*`). ✓

**Placeholder scan:** No TBD/TODO-in-logic. The single unverified external contract (obsidian-mcp `search_query` shape) is isolated to `_TASK_DQL`/`_row_value`, unit-tested via fakes, and validated in Task 8 Step 7 — called out explicitly, not left vague.

**Type consistency:** `OpenItem`/`CompletedItem`/`TaskRef`/`normalize_text`/`open_task_line`/`apply_open_items`/`apply_completed_items`/`existing_task_index` names and signatures are consistent across Tasks 3-8. `fetch_todos` returns `{"open", "completed"}` consumed unchanged in Task 8.
