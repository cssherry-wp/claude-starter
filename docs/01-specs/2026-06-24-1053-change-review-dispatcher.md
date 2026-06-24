# Spec: `change-review` as a review dispatcher + CI consolidation

**Date:** 2026-06-24
**Status:** Approved (design); ready for implementation planning

## Problem

The team's review tooling is fragmented and has a confusing name collision:

- A draft broad-checklist reviewer (`changereview.txt`, in `~/Downloads`) is unfiled and explicitly
  *avoids* invoking the deep reviewers — its correctness and security findings are dead-ends.
- Two genuinely different things are both called "code-review": the built-in `/code-review`
  (working-diff, correctness + reuse/simplification/efficiency, effort tiers, `--fix`/`--comment`)
  and the third-party `code-review` plugin (`anthropics/claude-code`; PR-by-number, 5 specialized
  agents, confidence scoring). Confirmed: the third-party plugin still exists.
- The SDLC `code-review.yml` workflow runs **two** Claude jobs — the third-party `code-review` plugin
  and a separate `/security-review` — duplicating orchestration and depending on the collision-prone
  plugin.

We want one well-defined broad reviewer that **dispatches** to the deep passes, a single CI job, and
a written map so humans know which reviewer to reach for.

## Goals

1. Land a `change-review` skill in `wp-labs-standards` that runs a broad read-only checklist **and**
   hands off to the deep reviewers, forwarding `--fix` / `--comment` / effort.
2. Fold deep **correctness** (`/code-review`) and deep **security** (`/security-review`) into
   `change-review`, so the standalone CI security job can be removed.
3. Make `--fix` / `--comment` span **all** of `change-review`'s steps, not just the `/code-review`
   forward.
4. Absorb the third-party plugin's unique angles (git-history context, prior-PR-comment continuity,
   inline-comment guidance, confidence scoring) so CI no longer needs that plugin.
5. Switch the SDLC `code-review.yml` to run `change-review` from `wp-labs-standards`, as one job.
6. Produce a full review-skills map (including read-only/built-in reviewers) and document the
   naming collision.
7. Apply the workflow change to every consuming repo under `~/code`.

## Non-goals (YAGNI)

- No merging of other review skills; no edits to built-in skills (`/code-review`, `/security-review`,
  `/review`) — they are positioned in the map only.
- No changes to `change-review`'s checklist logic beyond the hand-offs and absorbed angles.
- No other workflow changes.

## Design

### Component A — `change-review` skill

**Location:** `plugins/wp-labs-standards/skills/change-review/SKILL.md` (port of `changereview.txt`,
beside `github-pr-review` and `github-pr-prepare`). Frontmatter keeps `name: change-review` and
`user-invocable: true`; `argument-hint` updated to
`"[pr-number | pr-url] [--fix] [--comment] [--effort low|medium|high|max]"`.

**Base behavior (read-only):** the existing 7-point checklist — (1) summary, (2) outlying changes,
(3) architecture/security/structure risks, (4) lint/style on new files, (5) docs freshness,
(6) correctness, (7) tests — ending in a merge verdict (blockers/nits).

**Deep hand-offs (always fire; read-only unless a flag is passed):**

- **Point 6 (correctness)** → invokes built-in **`/code-review`** for the deep pass (replacing the
  former "defer, don't invoke" note).
- **Security slice of point 3** → invokes **`/security-review`** for deep vuln analysis. Architecture
  and structure stay native to `change-review`.
- Both reviewers operate on a **working diff**. Target resolution:
  - **No argument** → local uncommitted working diff: hand-offs run directly.
  - **PR number / URL** (local or CI) → the PR is materialized into a **throwaway git worktree**
    (`gh pr checkout` into a temp worktree, soft-reset the PR commits onto base so they appear as a
    working diff), reviewed there, then the worktree is discarded. The user's current branch and
    working tree are never disturbed.

**Absorbed angles (new lenses, from the third-party plugin):**

- **Git history/blame context** — read blame/history of modified code to surface bugs in light of how
  the code evolved.
- **Prior-PR-comment continuity** — scan earlier PRs that touched these files for review comments that
  may still apply.
- **Unified guidance compliance** — the existing CLAUDE.md/AGENTS.md convention check is **consolidated
  with inline-code-comment guidance** into a single "stated rules" check. A violation of any of
  CLAUDE.md, AGENTS.md, or relevant inline comments is a finding.

**Confidence scoring (transparency, not filtering):**

- Every finding carries a 0–100 confidence score.
- Scores **gate `--fix`**: only **high-confidence**, mechanically-fixable findings are auto-fixed.
  Lower-confidence findings are **never auto-fixed** — they are surfaced as **suggestions**.
- Findings are **not dropped** by score. **Every posted comment includes its confidence score.**

**`--fix` / `--comment` span all steps:**

- **`--fix`** applies high-confidence, mechanically-fixable findings across the whole review —
  lint/style (`--fix`/`--write` on new files), stale-doc updates, and correctness via
  `/code-review --fix`. Security and judgment-call findings are generally not auto-fixable.
- **`--comment`** posts **all** findings (every checklist point + both hand-offs), each with its
  confidence score.
- Combined: fix the fixable (high-confidence), comment the rest.
- Default (no flags): strictly read-only.

**Cross-references:** footer pointing to `github-pr-review` (handling comments after a review),
`requesting-code-review`, and the review-skills map.

### Component B — CI workflow (`code-review.yml`)

Collapse the two Claude jobs into one `code-review` job:

1. Checkout with `fetch-depth: 0`; keep the `[autofix]` skip detection and the `no-automation`
   label guard.
2. **Materialize** the PR diff into a working diff for the deep correctness pass — done in a side
   worktree so it does **not** disturb the real PR branch used for committing fixes.
3. Run `/wp-labs-standards:change-review --fix --comment` at **effort `high`** via
   `anthropics/claude-code-action@v1`, with
   `plugin_marketplaces` = this repo's marketplace git URL (read from the repo remote at
   implementation time) and `plugins: 'wp-labs-standards@wp-labs-starter'`.
4. **High-confidence fixes** are committed back to the PR branch as an `[autofix]` commit (the existing
   skip guard prevents re-review of that commit). **Un-fixable / lower-confidence** items are posted
   as PR comments, each **with its confidence score**.

Delete the standalone `security-review` job — its coverage now lives in `change-review`'s dispatch.

**Implementation caveats to resolve during build:**

- Keep the fix-commit path (real PR branch) separate from the review-materialization path (side
  worktree) so soft-reset never rewrites the PR's real history.
- Verify the built-in `/code-review`'s diff target (working-tree vs `base...HEAD`); its prompt is not
  on disk. If it can review `base...HEAD` directly, the materialization step simplifies.

### Component C — Review-skills map + cross-links

`plugins/wp-labs-standards/skills/change-review/review-skills-map.md`, linked from the repo README.
A single table positioning **all** reviewers and their lanes:

| Skill | Lane | Editable |
|---|---|---|
| `change-review` | Broad checklist + dispatch to deep passes; `--fix`/`--comment`/effort | yes (new) |
| `/code-review` (built-in) | Deep correctness + reuse/simplification/efficiency on working diff | no |
| `/security-review` (built-in) | Deep vuln audit of branch changes | no |
| `/review` (built-in) | Generic GitHub PR review (prompt not on disk; positioned only) | no |
| third-party `code-review` plugin | PR-by-number, 5 agents, confidence scoring | no |
| `requesting-code-review` | Process: ask for review before merge | yes |
| `receiving-code-review` | Process: handle feedback | yes |
| `github-pr-prepare` | Mechanics: open a PR | yes |
| `github-pr-review` | Plumbing: reply to / resolve PR comment threads | yes |

The doc includes:
- The hand-off chain: `change-review` → `/code-review` / `/security-review` → `requesting-code-review`
  → `github-pr-prepare` → `receiving-code-review` → `github-pr-review`.
- A **naming-collision callout**: `/code-review` (built-in) vs the `code-review` plugin vs
  `change-review`.
- A note that the plugin's git-history / prior-PR / inline-comment angles are **now absorbed** into
  `change-review`, so CI no longer needs the plugin (it remains available for ad-hoc use).

One-line "where this sits in the flow" cross-references added to `github-pr-review`,
`github-pr-prepare`, `requesting-code-review`, and `receiving-code-review`.

### Component D — Apply across repos

- **Source of truth:** the template at
  `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml` in
  `claude-starter`.
- **External consumer:** `translation_sdlc_demo` — its `.github/workflows/code-review.yml` is
  **identical** to the template today. Update its canonical (default-branch) copy; the linked worktree
  branches inherit the change on rebase/merge (do not separately edit transient worktree copies).
- Update `marketplace.json` (the `wp-labs-standards` description) and the scaffolding-sdlc docs to note
  that `wp-labs-standards` ships `change-review` and the workflow now runs it as one job.

## Acceptance criteria

- `change-review` skill exists in `wp-labs-standards`, runs the checklist, dispatches to `/code-review`
  and `/security-review`, and applies the absorbed angles and confidence scoring.
- `--fix` only modifies high-confidence findings; `--comment` posts all findings with scores; default
  is read-only.
- PR-by-number reviews run the deep passes via a throwaway worktree without disturbing the workspace.
- `code-review.yml` (template + `translation_sdlc_demo`) runs `change-review` at effort `high` via
  the split design (read-only `review` job → patch + findings artifact → privileged `apply` job);
  the `security-review` job is gone and the third-party plugin is no longer referenced. (See the
  "split CI workflow" revision note below — supersedes the original one-job intent above.)
- `review-skills-map.md` exists and is linked from the README; the four adjacent skills carry
  cross-references.

## Open implementation questions (deferred to planning)

- Exact `/code-review` diff target (see caveat) — drives whether the materialization step is needed.
- The marketplace git URL string for `claude-code-action` (read from remote at build time).

## Revision 2026-06-24: split CI workflow (security)

Two automated security reviews flagged the single `change-review` CI job (Component B) as a
CRITICAL prompt-injection→RCE risk: it ran the agent on untrusted PR content while holding
`contents: write` and pushing commits. Revised design (user-approved):

- **Two jobs.** `review` runs the agent with `permissions: contents: read` (no push, no
  comment) and writes an autofix patch + a findings file to an artifact. `apply` runs **no
  agent and no PR code** — it deterministically `git apply`s the patch, commits `--no-verify`,
  pushes, and posts the findings comment. The write-capable token lives only in `apply`.
- **Same-repo gate.** The agent runs only when `head.repo.full_name == github.repository`
  (fork PRs get no secrets and are reviewed by a human).
- **Marketplace pinned** to a commit SHA for supply-chain safety (best-effort given the
  action's input support; documented caveat).
- **Residual risks (bounded, not eliminated):** the model token still lives in the agent
  job (exfiltration possible if injected, limited to same-repo actors), and a malicious patch
  could still be committed to the *attacker-controlled PR branch* — caught by branch
  protection + required human review on the merge target. Consuming repos MUST branch-protect
  main/release and must not auto-merge on `[autofix]`/bot authorship.
