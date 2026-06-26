# Daily PR Listing

**Date:** 2026-06-24
**Status:** Draft for review
**Scope:** `plugins/wp-labs-planner` — the daily run lists GitHub PRs opened or closed in the last
day under the daily note's `## Notes`.

## Problem

The daily note surfaces calendar events, accomplishments, and learnings, but nothing about
GitHub activity. PRs you opened, merged, or that need your review go unrecorded.

## Goal

During the daily run, deterministically surface GitHub PR activity from the last 24h in two
places:

1. Under `## Notes` (below accomplishments): PRs **opened or closed in the window** that involve
   you — *Review requested* (as actionable checkbox tasks) and *Authored / assigned*.
2. Below `### Completed / Cancelled`: PRs **merged in the window** that you **reviewed** or
   **authored** — a record of completed review/merge work.

## Definitions

- **`gh` CLI:** GitHub's official CLI, already authenticated on the run host. The collector
  shells out to it (same `subprocess` pattern as `gitcommit.py`).
- **Window:** the last `lookback_hours` (default 24) measured from the run time.
- **Opened / closed in window:** `createdAt >= since` (opened) or `closedAt >= since` (closed).
- **Relationship tags:** which `@me` qualifier matched a PR — `review_requested`, `reviewed_by`,
  `author`, `assignee` — plus a `merged` tag for `is:merged` results. Not derivable from the
  search JSON, so carried from *which search* returned the PR.
- **Four groups** (mutually exclusive): *Merged by me*, *Reviewed by me* (the two merged-section
  blocks), *Review requested*, *Authored / assigned* (the two Notes-block groups).

## Behavior

### Fetch (gh CLI) — annotated PRs

A PR's relationship to you and its merged status are **not** in the `gh search prs` JSON
(the search API exposes `author`/`assignees` but no review-request/review/merged fields). So the
collector learns them from *which qualifier matched*. It runs these searches (each `--json
number,title,url,state,createdAt,closedAt,repository`, `--limit 100`):

| Search | Tags applied |
|--------|--------------|
| `review-requested:@me updated:>=<since>` | `review_requested` |
| `author:@me updated:>=<since>` | `author` |
| `assignee:@me updated:>=<since>` | `assignee` |
| `reviewed-by:@me is:merged merged:>=<since>` | `reviewed_by`, `merged` |
| `author:@me is:merged merged:>=<since>` | `author`, `merged` |

Results are **unioned by URL**, OR-ing the tags onto one `PullRequest` per PR. The `@me`
qualifiers span every repo you can access, so no repo/owner config is needed. For the non-merged
searches, window filtering is client-side: keep a PR only when `createdAt >= since` or
`closedAt >= since`.

### Classify into four disjoint groups

A pure classifier assigns each PR to exactly **one** group, in this precedence — so the overlaps
you flagged never double-count:

1. **Merged by me** — tagged `merged` + `author`.
2. **Reviewed by me** — tagged `merged` + `reviewed_by`, not already in *Merged by me*.
3. **Review requested** — not merged-in-window, tagged `review_requested`.
4. **Authored / assigned** — not merged-in-window, tagged `author` or `assignee`, not in
   *Review requested*.

Groups 1–2 render in the merged section; groups 3–4 in the Notes block. Per PR derive
`repo`/`number`/`title`/`url`, `state` (`open`/`merged`/`closed`), `event`
(`merged`/`closed`/`opened`), `when` (the in-window date).

### Render (deterministic, below "This Week So Far")

`build_notes_block` inserts this block directly **after** `### ✅ This Week So Far` and before the
learnings section:

```
### 🔀 Pull Requests
#### Review requested
- [ ] [owner/repo#12 Title](https://github.com/owner/repo/pull/12) — opened 2026-06-24
#### Authored / assigned
- [owner/repo#9 Title](https://github.com/owner/repo/pull/9) — merged 2026-06-24
```

- **Review requested** renders each PR as a `- [ ]` checkbox task, so it is actionable and shows
  up in the daily TODO Dataview. **Authored / assigned** renders as plain bullets.
- Empty subgroups are omitted; the whole block is omitted when there are no PRs.
- If the collector degraded (see Error handling), render a single `- ⚠️ Pull requests unavailable`
  line under the heading so the gap is visible.

### Merged PRs reviewed / authored by me (below `### Completed / Cancelled`)

A second deterministic section records the two merged-section groups (classifier groups 1–2):

- **Merged by me** — `merged` + `author` (interpreted as *your authored PRs that merged*, since
  GitHub search has no `merged-by:` qualifier).
- **Reviewed by me** — `merged` + `reviewed_by`.

The `### ✅ PRs reviewed & merged` heading is added to the **Daily.md template** directly below the
`### Completed / Cancelled` Dataview; the daily run **replaces** its body each run:

```
### ✅ PRs reviewed & merged
#### Merged by me
- [owner/repo#7 Title](https://github.com/owner/repo/pull/7) — merged 2026-06-24
#### Reviewed by me
- [owner/repo#5 Title](https://github.com/owner/repo/pull/5) — merged 2026-06-24
```

The four groups are disjoint (see precedence): a PR you both authored and reviewed lands in
*Merged by me* only. Empty subgroups are omitted; when both are empty the heading is left with no
items (it lives in the template). Degraded fetch renders the `- ⚠️ Pull requests unavailable` line
under the heading.

## Architecture

### Config — new `GithubCfg`

- `lookback_hours: int = 24`.

Loaded in `config.py` under a `github:` section (absent section → defaults). `Config` gains a
`github: GithubCfg` field.

### Collector — new `planner/collectors/github.py`

```python
@dataclass
class PullRequest:
    repo: str
    number: int
    title: str
    url: str
    state: str                 # open | merged | closed
    created_at: datetime
    closed_at: datetime | None
    tags: frozenset[str]       # subset of {review_requested, reviewed_by, author, assignee, merged}
    event: str                 # opened | closed | merged (derived for render)
    when: date                 # the in-window date (derived for render)

def fetch_involved_prs(cfg: GithubCfg, since: datetime) -> list[PullRequest]:
    """Return PRs involving @me, each annotated with its relationship/merged `tags`.

    Runs the five gh searches, unions by URL (OR-ing tags), and window-filters the
    non-merged results. Raises on gh failure (caller degrades).
    """

def classify_prs(prs: list[PullRequest]) -> dict:
    """Split annotated PRs into the four disjoint groups by precedence.

    Returns {"merged_by_me", "reviewed_by_me", "review_requested", "authored_assigned"},
    each a list[PullRequest]. Pure; no I/O.
    """
```

A private helper runs one `gh search prs` invocation and parses its JSON;
`fetch_involved_prs` composes the five calls and annotates; `classify_prs` is pure.

### Data flow — `daily.py::run_daily`

PRs are fetched **separately from the LLM payload** (deterministic, never sent to the model):

```python
since = datetime.now() - timedelta(hours=cfg.github.lookback_hours)
groups = _safe("github", lambda: github.classify_prs(
    github.fetch_involved_prs(cfg.github, since)))
path = render_daily(vault, cfg, synthesis, today, groups)
```

`render_daily` gains a `groups` parameter: it threads the two Notes groups into
`build_notes_block` (patched under `## Notes`) and patches the two merged groups under the
template's `### ✅ PRs reviewed & merged` heading.

### Rendering — `render_daily.py`

- `build_notes_block(synthesis: dict, groups: dict | str | None = None) -> str` — unchanged
  assembly plus the Notes PR block (groups 3–4) inserted after the accomplishments section.
- `_pr_block(groups: dict | str | None) -> str` — formats Review-requested as `- [ ]` tasks and
  Authored/assigned as bullets; the degraded warning line; `""` when both empty.
- `_merged_block(groups: dict | str | None) -> str` — formats the Merged-by-me / Reviewed-by-me
  sub-blocks (groups 1–2); `""` when both empty.
- `render_daily` patches `_merged_block(...)` under `### ✅ PRs reviewed & merged`, replacing the
  prior body (idempotent per run). A degraded `groups` (warning string) renders the warning line
  in both locations.

## File structure

| File | Change |
|------|--------|
| `planner/config.py` | add `GithubCfg`; `Config.github`; parse `github:` section |
| `planner/collectors/github.py` | **new** — `PullRequest`, `fetch_involved_prs`, `classify_prs`, gh JSON parsing |
| `planner/daily.py` | `run_daily` fetches+classifies PR groups via `_safe` and passes them to `render_daily` |
| `planner/render_daily.py` | `build_notes_block` + `_pr_block` + `_merged_block`; `render_daily` `groups` param + patch the merged heading |
| `templates/Daily.md` | add `### ✅ PRs reviewed & merged` heading below `### Completed / Cancelled` |
| `templates/config.example.yaml` | document the `github:` section |
| `tests/test_collectors_github.py` | **new** — fetch/parse/group/window/dedupe + merged fetches (mocked `gh`) |
| `tests/test_render_daily.py` | PR block (checkbox RR) + merged block placement/format/omission/degraded |
| `tests/test_config.py` | `github` defaults |

## Testing

- **`fetch_involved_prs`** (mock `subprocess.run` with canned `gh` JSON): unions by URL and ORs
  tags when a PR matches multiple searches; sets `repo`/`url`/`state`/dates; window filter drops
  non-merged PRs whose `createdAt`/`closedAt` are both before `since`; gh non-zero exit raises.
- **`classify_prs`** (pure, no mocking): the four groups are disjoint; a PR tagged `merged`+`author`
  lands in *Merged by me* (not *Reviewed by me* nor *Authored / assigned*); a PR tagged
  `review_requested`+`author` (not merged) lands in *Review requested*; empty input → four empty
  groups.
- **Render:**
  - `_pr_block`: Review-requested rendered as `- [ ]` tasks, Authored/assigned as bullets; omits
    empty subgroups; whole block omitted when both empty; placed immediately after
    `### ✅ This Week So Far`; degraded input → warning line.
  - `_merged_block`: both sub-blocks formatted; omitted when both empty; degraded → warning line.
  - `render_daily` patches the merged block under `### ✅ PRs reviewed & merged`, replacing prior
    content on a same-day re-run.
- **Config:** missing `github:` section yields `lookback_hours == 24`.

## Caveats / assumptions

- Requires `gh` installed and authenticated on the run host; otherwise the collector degrades to
  the warning line and the daily run continues (collector resilience matches gmail/onenote).
- `merged` vs `closed` distinction depends on a merged indicator being available from
  `gh search prs --json`; if the field is absent, closed-without-merge and merged both render as
  `closed` (the plan pins the exact JSON field after checking `gh search prs --json` output).
- Date filtering is client-side, so result-set size is bounded by `updated:>=` + `--limit 100`;
  an extremely active 24h beyond 100 PRs per search would truncate (acceptable; logged if hit).
- PRs are intentionally excluded from the LLM payload to keep the listing factual and reproducible.
- **"Merged by me" is an interpretation:** GitHub search has no `merged-by:` qualifier, so it
  resolves to *your authored PRs that merged in the window* (`author:@me is:merged`). If you meant
  "PRs whose merge button I clicked," that is not available via search and would need per-PR
  GraphQL (`mergedBy`) — out of scope unless you confirm you want it.
- The four groups are **disjoint** by the classifier's precedence: a PR merged in the window is
  pulled out of the Notes groups into the merged section, so it is never double-counted. (This is
  the overlap fix — `reviewed-by` vs `review-requested` and `author`/`assignee` vs the merged
  groups are resolved by tag precedence, not separate uncoordinated queries.)
- Patching `### ✅ PRs reviewed & merged` requires replacing a heading's body; if
  `vault.patch_heading` only appends, the plan adds a replace path (clear-then-append) so re-runs
  don't stack duplicates.
