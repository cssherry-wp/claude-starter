---
name: change-review
description: Review a changeset for a summary, surprises, architecture/security/structure risks, correctness bugs, test coverage, lint/style of new files, and doc freshness — dispatching deep correctness to /code-review and deep security to /security-review, with confidence-scored findings. Reviews the uncommitted working-tree diff by default, or a GitHub PR when given a PR number/URL. Trigger when the user asks to review their changes, review the diff, review a branch before pushing, or review a PR.
user-invocable: true
allowed-tools: Read, Bash, Grep, Glob, Agent, Skill, Edit, Write
argument-hint: "[pr-number | pr-url] [--fix] [--comment] [--effort low|medium|high|max]"
---

# Change review

Produce a focused review of a changeset against a fixed checklist, dispatching the
deep passes to `/code-review` (correctness) and `/security-review` (security). Read-only
by default — modify or comment only when `--fix`/`--comment` is passed.

## 0. Parse flags

From `$ARGUMENTS`, separate the target from the flags:

- `--fix` — after reviewing, apply **high-confidence**, mechanically-fixable findings
  (lint/style on new files, stale-doc edits, and correctness via `/code-review --fix`).
  Never auto-fix lower-confidence findings — surface them as suggestions.
- `--comment` — post **all** findings (every checklist point + both hand-offs) as comments,
  each **with its confidence score**.
- `--effort low|medium|high|max` — forwarded to `/code-review` (and used to scale the security
  pass). Defaults to the reviewer's own default tier when omitted.
- No flags → strictly read-only report.

## 1. Resolve the review target

Pick the target from the non-flag arguments:

- **No argument** → review the local **uncommitted** changes:
  - Tracked, staged + unstaged: `git diff HEAD`
  - Untracked new files: `git ls-files --others --exclude-standard` (then `Read` each)
  - Scope: `git status --short`
  - If the working tree is clean, fall back to this branch vs base:
    `git merge-base --fork-point origin/HEAD HEAD` (or `main`/`master`), then `git diff <base>...HEAD`.
    Tell the user that's what you reviewed.
  - The deep hand-offs (section 4) run directly against this working diff.
- **A PR number (`123`) or PR URL** → review that GitHub PR:
  - Title/body/branch: `gh pr view <n> --json title,body,headRefName,baseRefName,files`
  - Diff: `gh pr diff <n>` (`--patch` for full hunks)
  - **To run the deep hand-offs against a PR, materialize it as a working diff in a throwaway
    worktree** so the user's workspace is untouched:
    ```bash
    WT=$(mktemp -d)
    git worktree add --detach "$WT"
    BASE=$(gh pr view <n> --json baseRefName -q .baseRefName)
    git -C "$WT" fetch origin "$BASE"          # ensure origin/$BASE exists for the reset below
    git -C "$WT" fetch origin "pull/<n>/head"  # fetch PR head last → FETCH_HEAD points to it
    git -C "$WT" checkout FETCH_HEAD
    git -C "$WT" reset --soft "origin/$BASE"   # PR commits now appear as a working diff
    ```
    Run `/code-review` and `/security-review` from inside `$WT`, then
    `git worktree remove --force "$WT"`. If the worktree cannot be created (no PR fetch), do the
    checklist on `gh pr diff` and note that the deep passes were skipped (no working tree).

State at the top of your report exactly what was reviewed (e.g. "uncommitted working-tree changes:
9 files" or "PR #123: feat/foo → main").

**Ignore mechanical churn** when summarizing and hunting for issues: lockfiles
(`package-lock.json`, `yarn.lock`, `poetry.lock`, `Cargo.lock`), build output (`dist/`, `build/`,
`*.min.*`), vendored/`node_modules` dirs, and generated files (snapshots, codegen,
`*.generated.*`). Note their presence in one line, don't review their contents.

If the target is empty (no diff, no PR), say so and stop.

## 2. Detect repo conventions and stated rules

Before reviewing, learn how *this* repo lints, formats, documents, and what rules it states —
never assume a stack.

- **Lint/format tooling** (in order of authority): `package.json` scripts (`lint`, `format`,
  `typecheck`), `.eslintrc*`/`eslint.config.*`, `.prettierrc*`, `pyproject.toml`/`setup.cfg`
  (`ruff`, `black`, `flake8`, `isort`), `.rubocop.yml`, `go.mod` (`gofmt`/`golangci-lint`),
  `Cargo.toml` (`rustfmt`/`clippy`), `.editorconfig`, `Makefile` targets.
- **Stated rules (unified guidance check)** — treat all of these as one body of rules, and a
  violation of any as a finding: `CLAUDE.md`/`AGENTS.md`/`CONTRIBUTING*` and `docs/` style notes,
  **and inline code comments that state guidance** in or adjacent to the changed code (e.g.
  "// do not call this in a loop", "# keep in sync with X"). Note: CLAUDE.md is guidance written
  for an agent writing code, so not every instruction applies to review — judge relevance.
- **Docs surface**: `README*`, `docs/`, `AGENTS.md`, `CHANGELOG*`, in-repo `*.md`, and doc comments
  adjacent to changed code.

## 3. Gather historical and prior-review context

These lenses feed points (2) and (6) below — surface what they reveal as findings:

- **Git history / blame** of the modified code: `git log -n 20 --oneline -- <files>` and
  `git blame` on changed hunks. Flag changes that contradict why the code was last touched, or
  that reintroduce a previously-fixed bug.
- **Prior-PR-comment continuity**: for the changed files, look at recent merged PRs that touched
  them (`gh pr list --state merged --search "<path>"`, then `gh pr view <n> --comments`) and flag
  any earlier review comment that still applies to this change.

## 4. Run the checklist

Cover all seven points. Be specific: cite `file:line` and quote the relevant code. **Attach a
0–100 confidence score to every finding** (see section 5). Prefer high-signal findings over volume;
if a point has nothing to report, say "No issues" rather than padding.

**(1) Summary of the changes.** A short, faithful description grouped by theme/area — not a
file-by-file restatement. Lead with the primary intent.

**(2) Outlying changes.** Anything a reader would *not* predict from (1): unrelated edits, drive-by
refactors, changed behavior in untouched-seeming areas, dependency bumps, config/flag flips,
formatting churn mixed with logic, generated files, deletions. List each with `file:line` and one
line on why it's surprising. Incorporate anything the history/blame lens (section 3) surfaced.

**(3) Architecture / security / structure risks.** Call out anything forcing — or smuggling in — a
substantial change to architecture, security posture, or file structure: new cross-layer
dependencies/layering violations, new external surface (endpoints, public APIs),
auth/permission/RBAC changes, secrets/credentials, injection/SSRF/path-traversal/deserialization
risks, new dependencies (supply chain), data-model/migration changes, broad moves/renames, new
top-level dirs, or anything contradicting the stated rules from section 2. For each: severity
(high/med/low) and a suggested direction.
**Deep security hand-off:** always run `/security-review` against the working diff (the throwaway
worktree for PR targets), scoped to these changes, and fold its findings into this point. Forward
`--comment`/effort; security findings are generally not auto-fixable.

**(4) Lint/style on new files.** For every **newly added** file, verify it matches the repo's
linting/formatting and local conventions. Prefer running the real tools, scoped to the new files:
JS/TS `npx eslint <files>` / `npx prettier --check <files>`; Python `ruff check <files>` /
`black --check <files>`; Go `gofmt -l <files>`; Rust `rustfmt --check`; Ruby `rubocop <files>`.
Run from the directory that owns the tool config. **Filter to signal — do not report pre-existing
repo noise**: a warning that also fires on unrelated existing files is config noise, not a finding;
state when you've discounted warnings as such. (Existing files: only flag style issues you're
confident regress the repo norm.)

**(5) Documentation freshness.** Confirm docs that *should* reflect these changes do — `README`,
`docs/`, `AGENTS.md`, `CLAUDE.md`, CHANGELOG, command cheatsheets, env-var/config tables, public API
references, example snippets. Flag missing or stale docs with the specific file and what to add. If
doc-neutral, say so.

**(6) Correctness — deep hand-off.** Always invoke built-in **`/code-review`** against the working
diff (the throwaway worktree for PR targets) for the deep correctness + reuse/simplification/
efficiency pass; forward `--effort` and (with `--fix`) `--fix`. Fold its findings into this point.
Add your own high-confidence obvious-defect findings the deep pass missed and anything the
history/prior-PR lenses (section 3) surfaced.

**(7) Tests.** Whether changed/added behavior is covered. Did new logic get tests? Were existing
tests updated, or are any now stale/broken? Name the specific missing or affected test files. If
test-neutral (docs, config, pure formatting), say so.

## 5. Confidence scoring

Score every finding 0–100 for how confident you are it's a real, relevant issue:

- **0–49** — uncertain / possible false positive / pre-existing. Surface as a *suggestion* only.
- **50–79** — likely real but a nit or low-impact. Suggestion; never auto-fixed.
- **80–100** — verified, high-impact, or a direct stated-rule violation. Eligible for `--fix`.

Do **not** drop findings by score — report them all. With `--comment`, every comment shows its
score, e.g. `(confidence 85)`. With `--fix`, only findings ≥ 80 that are mechanically fixable are
applied; everything else is reported as a suggestion.

## 6. Apply / comment (only when flagged)

- **`--fix`**: apply the high-confidence fixes — run linters/formatters with `--fix`/`--write` on
  new files, edit stale docs, and run `/code-review --fix` for correctness. Locally, stage them so
  the user can review and commit. **In CI's split workflow the agent is read-only: apply fixes to
  the working tree only and do NOT commit, push, or comment — a separate privileged job stages the
  edits into an `[autofix]` commit and pushes it.** Report what was fixed vs left as a suggestion.
- **`--comment`**: post the report's findings as PR comments (use `github-pr-review` plumbing or
  `gh pr comment`), each with its confidence score; un-fixable and lower-confidence items go here.
  **In CI the agent instead writes all findings (with scores) to `change-review-findings.md`, and
  the separate privileged job posts that file as the PR comment.**

## 7. Output format

```
## Change review — <what was reviewed>

### 1. Summary
<grouped prose>

### 2. Outlying changes
- <file:line> — <why surprising> (confidence N)   (or: None)

### 3. Architecture / security / structure
- [HIGH/MED/LOW] <file:line> — <risk> → <direction> (confidence N)   (or: None)
  <deep security via /security-review folded in>

### 4. Lint & style (new files)
- <file> — <tool result / deviation + fix> (confidence N)   (or: All new files conform)

### 5. Docs
- <doc path> — <what needs updating> (confidence N)   (or: Up to date)

### 6. Correctness
- <file:line> — <bug + failure scenario> (confidence N)   (or: No obvious defects)
  <deep correctness via /code-review folded in>

### 7. Tests
- <test file / area> — <missing or stale coverage> (confidence N)   (or: Adequate / N/A)

### Verdict
**Blockers (fix before merge):**
- <ordered by severity>   (or: None)

**Nits (optional):**
- <minor items>   (or: None)

<if --fix: what was auto-fixed vs left as a suggestion>
<one line: safe to merge as-is, or address blockers first>
```

Keep it tight. End with the verdict, blockers first.

## Notes

- For large changesets, fan out with the Agent tool (one agent per area or checklist point) and
  synthesize — the final report must still follow the structure above.
- Respect the repo's own stated rules above generic priors.
- **Relationship to other review skills** (see `review-skills-map.md`): this skill is the broad
  dispatcher. `/code-review` (built-in) is the deep correctness + code-quality pass it calls;
  `/security-review` (built-in) is the deep vuln audit it calls. Note the **name collision**:
  built-in `/code-review` is *not* the third-party `code-review` plugin (PR-by-number, 5 agents) —
  this skill now absorbs that plugin's git-history, prior-PR, and inline-comment angles, so it is
  no longer needed in the review flow. After a review, `github-pr-review` handles replying to and
  resolving the resulting comment threads.
- **Implementation caveat:** built-in `/code-review` reviews the working diff; the worktree
  soft-reset above materializes a PR as one. If `/code-review` is confirmed to accept a
  `base...HEAD` target directly, the worktree step can be simplified.
