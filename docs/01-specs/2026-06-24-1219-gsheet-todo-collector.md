# Spec: Google Sheets todo collector for the daily planner

**Date:** 2026-06-24
**Status:** Approved (design); ready for implementation planning

## Problem

The daily planner's todo collector (`collectors/gdoc.py`) reads a Google **Doc** via the Docs API
(`documents().get`). The user's todos actually live in a Google **Sheet** with a structured
`Overview` tab, so the run fails with a 404 (`extract_doc_id` doesn't recognize `/spreadsheets/d/`,
and the Docs API can't read a spreadsheet regardless). The Sheet also carries richer state than a
flat doc — per-task status, completion timestamps, and carry-over age — that the current flat-text
pipeline throws away.

## Goals

1. Replace the Docs collector with a Sheets collector that reads the `Overview` tab.
2. Parse **open** items (the `Remaining items` cell) into Obsidian Tasks-syntax `- [ ]` lines with
   status-derived priority.
3. Detect **completed-but-undocumented** items (the `Completed:` block in the `Notes` cell) and
   backfill them into the daily note of the date they were completed, as `- [x] … ✅ <date>`.
4. Avoid duplicating tasks that already exist in the vault, via a Dataview query — and when a task
   already exists, reconcile its priority/status to the Sheet's latest state.
5. Keep the run resilient: a Sheets failure degrades, never aborts.

## Non-goals (YAGNI)

- No support for keeping a Google Doc source (Docs collector is removed, not branched).
- No weekly-stats surfacing (% Completed, Avg Time) in the daily note.
- No LLM involvement in task generation — tasks are a deterministic transform.
- No editing/writing back to the Sheet (read-only).

## Source format (the `Overview` tab)

Columns (located by **header name** in row 1, not fixed position):
`Week | % Completed | # Completed | Average Time (hrs) | Remaining items | Notes`

The collector reads the **last N+1 populated rows** (newest row = current week; `N` =
`google.weeks_back`, default 4). Reading recent prior weeks lets late-logged completions still be
caught by the undocumented-completed check.

**`Remaining items` cell** — one open item per line:
```
- - - - - - - Ask for talent review (Waiting: 11/22/2025, 8:26:55 AM)
- Fix budget currency conversion
```
- Leading `-` tokens = **carry-over weeks** (each `-` = one week carried; **0 dashes = new this week**).
- Optional trailing `(<Status>: <date>)` = current status. **Status may be multiple words**
  (`On Notice`, plus `Waiting`, `Started`, `Completed`), so the annotation regex matches
  `\(([A-Za-z][A-Za-z ]*):\s*<date>\)`.

**`Notes` cell** — dated journal lines plus a `Completed:` sub-section:
```
Notes:
2026/01/05: ...
Completed:
- - Update for US sprint (Completed: 1/5/2026, 4:22:35 AM)
- Create interview feedback (Started: 1/9/2026, 4:29:26 AM) (Completed: 1/9/2026, 4:41:30 AM)
```
- Lines under `Completed:` are completed items; a line may carry multiple annotations.
- Last `(Completed: <date>)` = completion time; `(Started: <date>)` = start time.
- Duration = Completed − Started when both are present.

**Date grammar:** `M/D/YYYY, H:MM:SS AM/PM`. A line that doesn't match the grammar falls through
as plain text (logged at WARNING), never crashes the run.

## Design

### 1. Parser — `collectors/gsheet.py`

`fetch_todos(sheets_service, sheet_id, tab, weeks_back) -> dict` reads the tab via
`spreadsheets.values.get`, finds columns by header, takes the last `weeks_back + 1` rows, and
returns:
```python
{
  "open": [OpenItem(text, status, carry_over_weeks, raw)],
  "completed": [CompletedItem(text, completed_at: date, started_at: date | None, raw)],
}
```
`text` is the **normalized** task text — the stable identity used for dedup. Normalization strips:
leading `-` tokens, **all trailing `(<Status>: <date>)` annotations** (status may be multi-word,
e.g. `On Notice`; open *and* completed lines), and any Tasks emoji/priority signifiers, then lowercases and collapses whitespace.
So `--- Ask for talent review (Waiting: 11/22/2025, …)` and `- Ask for talent review (On Notice: …)
(Completed: …)` both normalize to `ask for talent review` and are recognized as the same task.
Two small pure helpers — `parse_open_line` and `parse_completed_line` — hold the regex grammar so
they're unit-testable in isolation.

### 2. Priority / scheduling mapping

Open items render with Obsidian Tasks signifiers derived from status:

| Status | Priority | Extra |
|---|---|---|
| On Notice | `⏫` high | `📅 <end of week>` due date |
| Started | (none / normal) | `🛫 <start date>` if available |
| Waiting | `🔽` low | — (blocked on someone else) |
| (no status) | (none / normal) | — |

- **End of week** = the **Sunday** of the current week (`week_start + 6`, where `week_start` is Monday).
- Carry-over age is surfaced as a trailing ` (carried Nw)` note on the line; it does not by itself
  change priority.
- **Status** is carried on the rendered line as a tag (`#status/on-notice`, `#status/waiting`,
  `#status/started`) so it's visible and reconcilable. The status tag is *not* part of the
  normalized identity (so a status change doesn't read as a new task).

> These non-`On Notice` mappings, and the status-tag representation, are defaults chosen for sanity;
> confirm/adjust during spec review.

### 3. Dedup & reconcile via Dataview — `vault.search_query`

Before writing, run one Dataview DQL query through the existing MCP `search_query` to pull existing
task lines **with their file path** (so a match can be located and patched):
```
TABLE t.text, t.path, t.line, t.completion FROM -"zz-Templates" FLATTEN file.tasks AS t
```
Key existing tasks by **normalized text** (per §1). For each open item from the Sheet:

- **No match** → add it (per §4).
- **Match, signifiers already correct** → leave it untouched (idempotent re-runs).
- **Match, but priority / due-date / status tag differ from the Sheet's current state** → the Sheet
  is source of truth: **update the existing task line in place**. Read the matched note, locate the
  line by normalized identity, rewrite only its priority / `📅` due / `#status/*` signifiers (text
  and checkbox state untouched), and write back. E.g. a task that was `#status/waiting 🔽` last week
  and is now `On Notice` becomes `⏫ 📅 <Fri> #status/on-notice`.

Completed items are matched the same way; an already-documented completion is skipped. If the query
fails, log and proceed without dedup/reconcile (degrade, don't abort).

### 4. Placement & rendering

- **Open items** → today's daily note, appended under a new `## Open Items` heading (distinct from
  the existing dataview-driven `## TODO`), as `- [ ] <text> <priority> <due> #status/<status>`.
- **Completed-but-undocumented items** → **backfilled into the completion-date's daily note**:
  ensure that date's note exists (create a stub if missing, same mechanism as `ensure_daily_note`),
  then add `- [x] <text> ✅ <YYYY-MM-DD>` under its `## TODO`. Duration appended inline (e.g.
  ` (12m)`) when both Started and Completed are present.

Rendering lives in `render_daily.py` (open items) and a small backfill helper (completed items),
both fed by structured data — no LLM. The existing LLM synthesis continues to produce calls,
accomplishments, and learnings unchanged; only the `todos`→`new_tasks` path is replaced.

### 5. Wiring & config

- Remove `collectors/gdoc.py` and the Docs API client (`build_docs`). `_gather_daily` calls
  `gsheet.fetch_todos`.
- OAuth scope `documents.readonly` → `spreadsheets.readonly` (re-auth once; enable the **Google
  Sheets API** in Cloud Console).
- Config (`config.yaml` / `config.py`):
  - `google.gdoc_id` keeps its name but now holds a Sheets URL or bare ID; `extract_doc_id` learns
    `/spreadsheets/d/<id>`.
  - Add `google.overview_tab` (default `Overview`) and `google.weeks_back` (default `4`).
- The collector stays wrapped in `_safe()`.

### 6. Testing (TDD)

Unit tests with fixture cell-strings — no live Sheets/network:
- `parse_open_line`: dash-counting → carry-over weeks; each status; no status; malformed line.
- `parse_completed_line`: single + multiple annotations; Started+Completed duration; missing Started.
- Column-by-header location, including reordered headers and the last-N+1-rows window.
- Dedup & reconcile against a fake `search_query`:
  - absent → kept;
  - present with matching signifiers → untouched;
  - present with stale priority/status (e.g. Waiting→On Notice) → existing line patched in place
    (priority/due/status-tag rewritten, text + checkbox state preserved);
  - query failure → no dedup, run continues.
- Backfill against a fake Vault: asserts the completion-date note (created if missing) gets the
  `- [x] … ✅` line under `## TODO`; open items land under `## Open Items` in today's note.
- Priority mapping: On Notice → `⏫` + Friday due date + `#status/on-notice`.

## Resolved decisions

- Carry-over weeks = `dash_count`; **0 dashes = new this week**, each `-` = one more week carried.
- "End of week" = **Sunday** (`week_start + 6`).
- Status may be **multi-word** (`On Notice`); annotation regex accounts for it.
- Status carried as `#status/<status>` tag; confirmed acceptable.

## Remaining assumptions (adjust any time)

- Non-`On Notice` priority defaults (§2): `Waiting → 🔽`, `Started → 🛫 start`, no-status → normal.
