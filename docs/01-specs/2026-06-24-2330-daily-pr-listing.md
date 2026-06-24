# Daily PR Listing

**Date:** 2026-06-24
**Status:** Draft for review
**Scope:** `plugins/wp-labs-planner` — the daily run lists GitHub PRs opened or closed in the last
day under the daily note's `## Notes`.

## Problem

The daily note surfaces calendar events, accomplishments, and learnings, but nothing about
GitHub activity. PRs you opened, merged, or that need your review go unrecorded.

## Goal

During the daily run, list the pull requests **opened or closed in the last 24h** that involve
you, grouped by your relationship to them, rendered deterministically below the accomplishments
section.

## Definitions

- **`gh` CLI:** GitHub's official CLI, already authenticated on the run host. The collector
  shells out to it (same `subprocess` pattern as `gitcommit.py`).
- **Window:** the last `lookback_hours` (default 24) measured from the run time.
- **Opened / closed in window:** `createdAt >= since` (opened) or `closedAt >= since` (closed).
- **Groups:** *Review requested* (review requested from you) and *Authored / assigned*
  (authored by or assigned to you).

## Behavior

### Fetch (gh CLI)

Three searches via `gh search prs --json number,title,url,state,createdAt,closedAt,repository`
(plus an `updated:>=<since-date>` qualifier and `--limit 100` to bound results):

- `--review-requested=@me`
- `--author=@me`
- `--assignee=@me`

The `@me` qualifiers already span **every repo you can access**, so no repo/owner config is
needed. Date filtering is done **client-side** for precision and testability: keep a PR only when
`createdAt >= since` or `closedAt >= since`.

### Group, dedupe, classify

- **review_requested** = results of the review-requested search (in window).
- **authored_assigned** = (author ∪ assignee results, in window) **minus** anything already in
  review_requested. *Review-requested takes precedence* — a PR in both appears once, under
  Review requested.
- Dedupe within each group by URL.
- Per PR derive: `repo` (`owner/name`), `number`, `title`, `url`, `state` (`open`/`merged`/
  `closed`), `event` (`closed` when `closedAt` is in window, else `opened`), `when` (the in-window
  date).

### Render (deterministic, below "This Week So Far")

`build_notes_block` inserts this block directly **after** `### ✅ This Week So Far` and before the
learnings section:

```
### 🔀 Pull Requests
#### Review requested
- [owner/repo#12 Title](https://github.com/owner/repo/pull/12) — opened 2026-06-24
#### Authored / assigned
- [owner/repo#9 Title](https://github.com/owner/repo/pull/9) — merged 2026-06-24
```

- Empty subgroups are omitted; the whole block is omitted when there are no PRs.
- If the collector degraded (see Error handling), render a single `- ⚠️ Pull requests unavailable`
  line under the heading so the gap is visible.

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
    state: str   # open | merged | closed
    event: str   # opened | closed
    when: date

def fetch_prs(cfg: GithubCfg, since: datetime) -> dict:
    """Return {"review_requested": [PullRequest...], "authored_assigned": [PullRequest...]}.

    Runs the three gh searches, filters to the window client-side, classifies and
    dedupes with review-requested precedence. Raises on gh failure (caller degrades).
    """
```

A private helper runs one `gh search prs` invocation and parses its JSON; `fetch_prs` composes
the three, applies the window filter, and builds the two groups.

### Data flow — `daily.py::run_daily`

PRs are fetched **separately from the LLM payload** (deterministic, never sent to the model):

```python
since = datetime.now() - timedelta(hours=cfg.github.lookback_hours)
prs = _safe("github", lambda: github.fetch_prs(cfg.github, since))
path = render_daily(vault, cfg, synthesis, today, prs)
```

`render_daily` gains a `prs` parameter and threads it into `build_notes_block(synthesis, prs)`.

### Rendering — `render_daily.py`

- `build_notes_block(synthesis: dict, prs: dict | str | None = None) -> str` — unchanged assembly
  plus the PR block inserted after the accomplishments section.
- `_pr_block(prs: dict | str | None) -> str` — formats the grouped list (or the degraded warning
  line); returns `""` when there are no PRs.

## File structure

| File | Change |
|------|--------|
| `planner/config.py` | add `GithubCfg`; `Config.github`; parse `github:` section |
| `planner/collectors/github.py` | **new** — `PullRequest`, `fetch_prs`, gh JSON parsing |
| `planner/daily.py` | `run_daily` fetches PRs via `_safe` and passes them to `render_daily` |
| `planner/render_daily.py` | `build_notes_block` + `_pr_block`; `render_daily` `prs` param |
| `templates/config.example.yaml` | document the `github:` section |
| `tests/test_collectors_github.py` | **new** — fetch/parse/group/window/dedupe (mocked `gh`) |
| `tests/test_render_daily.py` | PR block placement/format/omission/degraded |
| `tests/test_config.py` | `github` defaults |

## Testing

- **Collector** (mock `subprocess.run` with canned `gh` JSON):
  - parses PRs; classifies `opened` vs `closed`/`merged`; sets `repo`/`url`/`when`.
  - window filter drops PRs whose `createdAt`/`closedAt` are both before `since`.
  - dedupes by URL; review-requested precedence removes the dupe from authored_assigned.
  - empty results → both groups empty; gh non-zero exit raises.
- **Render:** `_pr_block` formats both groups; omits empty subgroups; whole block omitted when no
  PRs; placed immediately after `### ✅ This Week So Far`; degraded input → warning line.
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
