# Weekly Template Redesign

**Date:** 2026-06-24
**Status:** Draft for review
**Scope:** `plugins/wp-labs-planner` — the weekly overview note and its renderer/synthesis

## Problem

The current weekly overview template (`templates/Weekly.md`) has gaps and redundancy:

- `## Highlights` is never populated — nothing in the renderer or synthesis fills it.
- Three overlapping task views: a dynamic `## Open tasks by project` Dataview, a frozen
  `## Snapshot (frozen)` block, and a `## From the weekly planner` Dataview filtered on the
  `#weekly-planner` provenance tag.
- Project statuses live in their own `## Project statuses` section, detached from the tasks
  they describe.
- No view of what was *in progress*, *completed*, or *cancelled* during the week.
- `## References` lists all `#Weekly`-tagged list items ever, not files created that week.
- No learnings/follow-ups rollup.

## Goal

Restructure the weekly note into a clear point-in-time record (frozen blocks injected by
Python) plus live, project-grouped Dataview queries that always reflect current vault state.

## Definitions

- **Frozen block:** Markdown injected by `render_weekly.py` at generation time. A permanent
  snapshot of the moment the weekly note was built.
- **Live query:** A Dataview code block that re-evaluates inside Obsidian every time the note
  is opened.
- **Week range:** Monday–Sunday of `gen_day`'s week. `week_end` already exists
  (`render_tasks.week_end`); a matching `week_start` (Monday) will be added.
- **Task markers:** `[ ]` todo, `[/]` or `[\]` in progress, `[-]` cancelled, `[x]` completed.
- **Priority emoji:** 🔺 highest, ⏫ high, 🔼 medium, 🔽 low, ⏬ lowest (Obsidian Tasks).

## New section layout (top → bottom)

| # | Section | Type | Contents |
|---|---------|------|----------|
| 1 | `## Highlights` | frozen | LLM-generated short bullets of the week's narrative |
| 2 | `## Open tasks by project` | frozen | Per project `### [[00-Name\|Name]]`: a couple status bullets (status + timeline assessment), then that project's open tasks, urgent first |
| 3 | `## Open tasks (current)` | live | All open tasks (`!completed AND status != "-"`); grouped by project, sorted by priority |
| 4 | `## In progress this week` | live | `status = "/" OR status = "\"`; grouped by project, sorted by priority |
| 5 | `## Learnings & Follow-ups` | frozen | LLM rollup of the week's daily-note learnings, each linked to its source daily |
| 6 | `## References` | live | Files **created** this week (`file.cday` in week range); ungrouped, sorted by creation time (newest first) |
| 7 | `## Completed this week` | live | `completed AND completion` in week range; grouped by project, sorted by priority |
| 8 | `## Cancelled this week` | live | `status = "-"` with ❌ date (fallback `file.day`) in week range; grouped by project, sorted by priority |

Removed sections: `## Snapshot (frozen)`, `## From the weekly planner`, standalone
`## Project statuses` (folded into section 2).

## Grouping & sorting (live task queries)

Applies to the four task queries (Open tasks (current), In progress, Completed, Cancelled):

- **Group by** the project tag: `filter(tags, (t) => startswith(t, "#project/"))[0]`, with an
  "Ungrouped" fallback for tasks without a `#project/` tag.
- **Sort by** priority, highest first. Dataview does not parse Tasks priority natively, so the
  DQL computes a numeric sort key from the priority emoji present in the task text (🔺=0 … ⏬=4,
  none=5). Exact expression pinned in the implementation plan.

**References** is the exception: it is ungrouped and sorted by file creation time
(`file.cday`/`file.ctime`), newest first.

## Week range injection

`build_weekly_body` already replaces `{{week}}`. It will also replace:

- `{{week_start}}` → Monday (ISO) of `gen_day`'s week
- `{{week_end}}` → Sunday (ISO)

Live date-scoped queries reference these as `date("YYYY-MM-DD")` literals, keeping the rendered
note deterministic and unit-testable as text.

## Synthesis changes

`templates/prompts/weekly_synthesis.md` output schema gains two fields:

```jsonc
{
  "highlights": ["<short highlight>", ...],
  "learnings": [{"text": "<learning or follow-up>", "source": "<daily note name>"}, ...],
  "projects": [ ... ],   // unchanged
  "groups": [ ... ]      // unchanged
}
```

`weekly.py::_gather_weekly` adds the week's daily-note content to the payload (reusing
`collectors.vault.recent_notes`) so the LLM can roll up learnings and link each to its source
daily note.

## Renderer changes (`render_weekly.py`)

- `build_weekly_body`: replace `{{week}}`/`{{week_start}}`/`{{week_end}}`; inject Highlights
  (section 1), the grouped Open-tasks-by-project block with per-project status bullets
  (section 2), and Learnings & Follow-ups (section 5).
- Rename `_snapshot_block` → `_open_tasks_block`; under each `### [[00-Name|Name]]` emit a
  couple status bullets (status, timeline assessment) before the task lines.
- Add `_highlights_block(synthesis)` and `_learnings_block(synthesis)` (the latter renders each
  item as a bullet linking to its source daily note).
- Drop the standalone `_statuses_block` injection (its content moves into `_open_tasks_block`).
- Project-note `## Status` / `## Timeline` updates are unchanged.
- Add a `week_start` helper (Monday) alongside the existing `week_end`.

## Testing

- Live Dataview blocks are inert text; tests assert the rendered markdown structure (headings,
  query bodies, `GROUP BY`/`SORT` clauses, injected `{{week_start}}`/`{{week_end}}` literals),
  not query results.
- New/updated tests in `tests/test_render_weekly.py`:
  - Highlights block injected from synthesis `highlights`.
  - Open-tasks-by-project block carries per-project status bullets before tasks, urgent first.
  - Learnings block links each item to its source daily.
  - `{{week_start}}` / `{{week_end}}` replaced with the correct Mon/Sun ISO dates.
  - Removed sections absent; new section headings present in the packaged default.
- Update `test_load_default_weekly_template_has_expected_headings` for the new headings (it
  currently asserts `## Snapshot (frozen)` and `#weekly-planner`, both removed).

## Folded-in additions

Two small, related changes ride along with this redesign (a third — per-person context in
project notes and `People.md` — is deferred to its own spec, as it is a new LLM subsystem):

### A. Tag the daily event time line with the project hash

`render_daily.build_notes_block` already renders the event header as `### <title> #project/<Name>`.
Also append the event's `#project/<Name>` to its time bullet, so the dated line carries the tag:
`- <time> #project/<Name>` (omit the trailing tag when the project is blank). This makes the
dated event line addressable by `#project/` Dataview/Tasks queries.

### B. Configurable `notes_dir` scanned by the weekly run

Add an optional `notes_dir` field to `VaultCfg` (default `""` = disabled). When set, the weekly
run also looks at markdown under `notes_dir`, in addition to `projects_dir`:

- `collectors.vault.open_tasks` scans `notes_dir` markdown for `- [ ]` tasks (so the live/frozen
  open-task views and the synthesis payload include them).
- `weekly._gather_weekly` adds `notes_dir` file contents to the payload (`payload["notes"]`) so
  the LLM can draw highlights/learnings from them.

A new public collector `notes_under(vault, cfg) -> list[RecentNote]` returns the `notes_dir`
markdown (empty list when unset); both call sites use it.

## Caveats / assumptions

- **Cancelled date:** depends on the Obsidian Tasks plugin exposing the ❌ date to Dataview;
  if unavailable, the query falls back to `file.day` within the week range. Confirmed in the plan.
- **In progress "this week":** `[/]`/`[\]` is a current-state marker, not a dated event; the
  query shows tasks currently in progress (best-effort week scoping via 🛫 where present).
- **Priority sort** relies on the priority emoji being present in task text (it is, via
  `priority_emoji`); tasks with no priority sort last.
- `#weekly-planner` tag still stamps Sheet-sourced tasks for dedup; it simply no longer has its
  own surfaced section.
- Live query results cannot be verified in unit tests — only the generated query text.
- `notes_dir` content is read twice per weekly run (once by `open_tasks` for task scanning,
  once by `notes_under` for payload content). Acceptable for an infrequent batch job.
- The daily time-line tag is only added when the event has a time bullet; time-less events keep
  the project hash on the header only.
