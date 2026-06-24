# Per-Person Context (Weekly People Sync)

**Date:** 2026-06-24
**Status:** Draft for review
**Scope:** `plugins/wp-labs-planner` — the weekly run writes per-person context into project
notes (`## Members`) and maintains one-line descriptions in `People.md`.
**Depends on:** the weekly-template-redesign spec (`2026-06-24-1753`), specifically the
`notes_dir` collector and the week-dailies payload that this feature reads from.

## Problem

`People.md` is a flat list of `#category/first_last` tags with no prose. Project notes list
members but nothing keeps "who is doing what" current. The weekly run already gathers the
week's daily notes (and, with `notes_dir`, a notes folder) but does nothing with the people
mentioned there.

## Goal

During the weekly run, for every person who appears in the analyzed files, (1) keep a single
up-to-date sentence about them in `People.md`, and (2) maintain a growing, dated, in-depth
context under each project's `## Members` section.

## Definitions

- **Analyzed files:** the files the weekly run reads — this week's daily notes plus any
  `notes_dir` markdown (the payload's `dailies` + `notes`).
- **People.md:** `{templates_dir}/People.md` (see `daily._people_path`). Sections are non-`#`
  label lines; each person is a `#category/first_last` tag line.
- **One-liner:** a single sentence describing what a person does / is working on.
- **Member entry:** in a project note's `## Members` section, a tag line carrying the one-liner,
  with dated in-depth sub-bullets beneath it.

## Behavior

### People.md (one-liner, upserted)

New inline format, one line per person:

```
## VIP
#vip/ray_rouleau — Leads VIP infra; currently driving the migration.
```

- The one-liner is **replaced** on each run (honors "update if the role changed"; the LLM is
  given the current sentence and returns it unchanged when nothing changed).
- A **newly-seen** person is **inserted** under the section matching their project, creating a
  `## <Project>` section when none matches. Their tag category approximately matches the project
  name (e.g. project "VIP" → `#vip/first_last`); the LLM proposes the tag and the renderer
  places it under the best-matching existing section, else a new one.
- `people.parse_people_tags` changes to read only the **first whitespace token** of each `#`
  line, so the em-dash summary never breaks attendee matching (`#vip/ray_rouleau — …` →
  `#vip/ray_rouleau`).

### Project note `## Members` (in-depth, growing)

```
## Members
- #vip/ray_rouleau — Leads VIP infra; currently driving the migration.
  - 2026-06-24 — Drove the cutover plan; coordinating with the vendor.
  - 2026-06-17 — Kicked off migration design.
```

- The member **top line mirrors the People.md one-liner** (upserted/replaced).
- Each run **prepends a dated in-depth sub-bullet** (`  - <gen_day> — <update>`), newest-first.
  Re-running on the same `gen_day` **replaces** that day's sub-bullet (idempotent per day).
- A person active on a project but **not yet listed** in `## Members` is **added** here, and
  also added to `People.md` (per the rule above). `## Members` is created if the note lacks it.

## Architecture (LLM emits structured data; renderer upserts)

The LLM produces language; the renderer does deterministic, testable file merging.

### Synthesis

`templates/prompts/weekly_synthesis.md` gains a `people` array:

```jsonc
"people": [
  {"tag": "#vip/ray_rouleau", "project": "VIP",
   "one_liner": "Leads VIP infra; currently driving the migration.",
   "update": "Drove the cutover plan; coordinating with the vendor."}
]
```

Instructions: derive people only from `payload.dailies` / `payload.notes`; one entry per
(person, project) the person is active on; reuse existing tags from `payload.people_template`;
keep `one_liner` to one sentence; `update` is the in-depth note for this run; when a person is
new, propose a tag whose category approximates the project name.

### Payload

`weekly._gather_weekly` adds `payload["people_template"]` = current `People.md` content (read via
`daily._people_path`, `""` when absent). Project notes are already in the payload with their
`## Members`, so the LLM extends rather than duplicates.

### Renderer — new module `planner/render_people.py`

Pure functions (no I/O), each `str -> str`:

- `upsert_people_template(content: str, entries: list[dict]) -> str` — for each distinct tag, set
  or replace the inline one-liner; insert a new tag under the section matching its project
  (create `## <Project>` when none matches). De-dupes by tag (first one-liner wins).
- `update_project_members(content: str, project: str, entries: list[dict], gen_day: date) -> str`
  — ensure `## Members`; upsert each member top line `- #tag — one_liner`; prepend/replace the
  `  - <gen_day> — <update>` sub-bullet **indented directly beneath that person's own member
  line** (each person owns their own dated sub-bullets — never a shared flat list); add missing
  members.

`render_weekly.render_weekly` calls these with `synthesis["people"]`, the projects, and
`gen_day`; writes `People.md` and each touched project note; returns those paths in `touched`.

## File structure

| File | Change |
|------|--------|
| `planner/people.py` | `parse_people_tags` reads only the first token of each `#` line |
| `planner/render_people.py` | **new** — `upsert_people_template`, `update_project_members` |
| `planner/render_weekly.py` | call the people renderer; add People.md + project notes to `touched` |
| `planner/weekly.py` | payload gains `people_template` |
| `templates/prompts/weekly_synthesis.md` | add `people` to the output schema + instructions |
| `tests/test_people.py` | cover inline-summary parsing |
| `tests/test_render_people.py` | **new** — upsert/insert/append/idempotency |
| `tests/test_render_weekly.py` | wiring: People.md + members written |
| `tests/test_weekly.py` | payload includes `people_template` |

## Testing

- `parse_people_tags` returns clean tags from lines with em-dash summaries.
- `upsert_people_template`: replace an existing one-liner; insert a new person under a matching
  section; create a `## <Project>` section when none matches; de-dupe by tag.
- `update_project_members`: create `## Members` when absent; upsert the top line; prepend a dated
  sub-bullet newest-first; replace the same-day sub-bullet on re-run; add a brand-new member.
- Wiring: `render_weekly` writes `People.md` and the project note and lists them in `touched`.
- Payload: `_gather_weekly` includes `people_template`.

## Caveats / assumptions

- One People.md one-liner per person (global). If the LLM emits differing one-liners for the same
  tag across projects, the renderer keeps the first; project-specific nuance lives in `## Members`.
- The LLM proposes tags/categories; "category ≈ project name" is best-effort. Mis-sorted people
  can be recategorized by hand (same as the daily flow's `#unsorted/...`).
- Idempotency is per `gen_day`: a same-day re-run replaces that day's sub-bullet but does not
  rewrite history from earlier days.
- Quality of one-liners/updates depends on the LLM and the analyzed files; sparse weeks yield
  sparse updates. The run never aborts if `People.md` is missing (treated as empty).
