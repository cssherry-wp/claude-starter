# change-review Dispatcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land a `change-review` skill that runs the broad checklist and dispatches deep correctness/security passes, then point CI and the review-skills map at it.

**Architecture:** `change-review` (a `wp-labs-standards` skill) is a read-only broad reviewer that hands deep correctness to built-in `/code-review` and deep security to `/security-review`, absorbs the third-party plugin's git-history/prior-PR/inline-comment angles, scores findings by confidence, and supports `--fix`/`--comment` across all steps. The SDLC `code-review.yml` collapses to one `change-review` job; a map doc positions all reviewers.

**Tech Stack:** Markdown skills, GitHub Actions YAML, `anthropics/claude-code-action@v1`, `gh` CLI, git worktrees.

## Global Constraints

- Spec: `docs/01-specs/2026-06-24-1053-change-review-dispatcher.md` — every task implicitly serves it.
- Marketplace plugin ref for CI: `wp-labs-standards@wp-labs-starter`; marketplace git URL: `https://github.com/cssherry-wp/wp-labs-starter.git`.
- Do **not** edit built-in skills (`/code-review`, `/security-review`, `/review`) — position in the map only.
- `--fix` modifies only **high-confidence** findings; lower-confidence findings are suggestions, never auto-fixed. Every posted comment includes its confidence score. Default (no flags) is strictly read-only.
- Confidence findings are **not dropped** by score (unlike the third-party plugin); the score is surfaced.
- Commit after each task. Branch is `feat/wp-labs-planner` (not main) — commit directly; follow the team commit-message format.

## File Structure

- `plugins/wp-labs-standards/skills/change-review/SKILL.md` — **create**: the dispatcher skill.
- `plugins/wp-labs-standards/skills/change-review/review-skills-map.md` — **create**: the map doc.
- `plugins/wp-labs-standards/skills/{github-pr-review,github-pr-prepare}/SKILL.md` — **modify**: add cross-ref footer.
- `plugins/wp-labs-superpowers/skills/{requesting-code-review,receiving-code-review}/SKILL.md` — **modify**: add cross-ref footer.
- `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml` — **modify**: one `change-review` job; drop `security-review`.
- `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/SKILL.md` — **modify**: note workflow now runs change-review.
- `.claude-plugin/marketplace.json` — **modify**: add `change-review` to the `wp-labs-standards` description.
- `README.md` — **modify**: link the map; list `change-review`.
- `~/code/translation_sdlc_demo/.github/workflows/code-review.yml` — **modify**: mirror the template.

---

### Task 1: Create the `change-review` skill

**Files:**
- Create: `plugins/wp-labs-standards/skills/change-review/SKILL.md`

**Interfaces:**
- Produces: a user-invocable skill `change-review` with argument-hint `[pr-number | pr-url] [--fix] [--comment] [--effort low|medium|high|max]`. CI (Task 4) invokes it as `/wp-labs-standards:change-review --fix --comment` at effort `high`.
- Consumes: built-in `/code-review` and `/security-review` (invoked via the Skill mechanism / prompt).

- [ ] **Step 1: Write the skill file**

Create `plugins/wp-labs-standards/skills/change-review/SKILL.md` with exactly this content:

````markdown
---
name: change-review
description: Review a changeset for a summary, surprises, architecture/security/structure risks, correctness bugs, test coverage, lint/style of new files, and doc freshness — dispatching deep correctness to /code-review and deep security to /security-review, with confidence-scored findings. Reviews the uncommitted working-tree diff by default, or a GitHub PR when given a PR number/URL. Trigger when the user asks to review their changes, review the diff, review a branch before pushing, or review a PR.
user-invocable: true
allowed-tools: Read, Bash, Grep, Glob, Agent, Skill, Edit
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
    git -C "$WT" fetch origin "pull/<n>/head"
    BASE=$(gh pr view <n> --json baseRefName -q .baseRefName)
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
  new files, edit stale docs, and run `/code-review --fix` for correctness. Stage them; in CI they
  are committed as an `[autofix]` commit (the workflow handles the commit). Report what was fixed vs
  left as a suggestion.
- **`--comment`**: post the report's findings as PR comments (use `github-pr-review` plumbing or
  `gh pr comment`), each with its confidence score. Un-fixable and lower-confidence items go here.

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
````

- [ ] **Step 2: Verify the skill file is well-formed**

Run:
```bash
cd /Users/sherryzhou/code/claude-starter
head -7 plugins/wp-labs-standards/skills/change-review/SKILL.md
grep -c '^## ' plugins/wp-labs-standards/skills/change-review/SKILL.md
grep -E '^\*\*\([1-7]\)' plugins/wp-labs-standards/skills/change-review/SKILL.md | wc -l
```
Expected: frontmatter shows `name: change-review` / `user-invocable: true`; at least 7 `## ` sections; the `wc -l` on checklist points prints `7`.

- [ ] **Step 3: Commit**

```bash
git add plugins/wp-labs-standards/skills/change-review/SKILL.md
git commit -m "feat(change-review): add review dispatcher skill"
```

---

### Task 2: Review-skills map + README link

**Files:**
- Create: `plugins/wp-labs-standards/skills/change-review/review-skills-map.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: the `change-review` skill from Task 1 (referenced by name).

- [ ] **Step 1: Write the map doc**

Create `plugins/wp-labs-standards/skills/change-review/review-skills-map.md`:

````markdown
# Review skills map

Which reviewer to reach for, and how they hand off.

| Skill | Lane | Editable here |
|---|---|---|
| `change-review` | Broad checklist + dispatch to the deep passes; `--fix`/`--comment`/`--effort` | yes (this plugin) |
| `/code-review` (built-in) | Deep correctness + reuse/simplification/efficiency on the working diff | no |
| `/security-review` (built-in) | Deep vulnerability audit of branch changes | no |
| `/review` (built-in) | Generic GitHub PR review | no |
| `code-review` plugin (`anthropics/claude-code`) | PR-by-number, 5 specialized agents, confidence scoring | no (third-party) |
| `requesting-code-review` | Process: ask for a review before merge | yes |
| `receiving-code-review` | Process: handle review feedback | yes |
| `github-pr-prepare` | Mechanics: open a PR | yes |
| `github-pr-review` | Plumbing: reply to / resolve PR comment threads | yes |

## Hand-off chain

`change-review` (broad scan; dispatches the deep passes)
→ `/code-review` (deep correctness) and `/security-review` (deep security)
→ `requesting-code-review` → `github-pr-prepare` → `receiving-code-review`
→ `github-pr-review` (resolve the resulting threads).

## Naming collision

Three different things sit near the name "code-review":

- **`/code-review`** (built-in) — reviews the **working diff** for correctness + code quality;
  effort tiers; `--fix`/`--comment`. This is what `change-review` calls for deep correctness.
- **`code-review` plugin** (`anthropics/claude-code`) — reviews a **PR by number** with 5 agents
  and confidence scoring. Still exists, but `change-review` now absorbs its unique angles
  (git-history context, prior-PR-comment continuity, inline-comment guidance, confidence scoring),
  so the team review flow and CI no longer use it. Disable it if the duplicate name causes confusion.
- **`change-review`** (this plugin) — the broad dispatcher described above.
````

- [ ] **Step 2: Link the map from the README and list the skill**

In `README.md`, line 15, change the `wp-labs-standards` skill list to include `change-review`. Replace:
```
plus** the common-task workflows `/commit` (structured commit-message format), `github-pr-prepare`, and `github-pr-review`.
```
with:
```
plus** the common-task workflows `/commit` (structured commit-message format), `change-review` (broad review dispatcher — see [review-skills map](plugins/wp-labs-standards/skills/change-review/review-skills-map.md)), `github-pr-prepare`, and `github-pr-review`.
```

- [ ] **Step 3: Verify links resolve**

Run:
```bash
cd /Users/sherryzhou/code/claude-starter
test -f plugins/wp-labs-standards/skills/change-review/review-skills-map.md && echo MAP_OK
grep -q "review-skills-map.md" README.md && echo README_OK
```
Expected: `MAP_OK` and `README_OK`.

- [ ] **Step 4: Commit**

```bash
git add plugins/wp-labs-standards/skills/change-review/review-skills-map.md README.md
git commit -m "docs(change-review): add review-skills map and README link"
```

---

### Task 3: Cross-reference the four adjacent skills

**Files:**
- Modify: `plugins/wp-labs-standards/skills/github-pr-review/SKILL.md`
- Modify: `plugins/wp-labs-standards/skills/github-pr-prepare/SKILL.md`
- Modify: `plugins/wp-labs-superpowers/skills/requesting-code-review/SKILL.md`
- Modify: `plugins/wp-labs-superpowers/skills/receiving-code-review/SKILL.md`

- [ ] **Step 1: Append a flow pointer to each skill**

Append this block (verbatim) to the END of each of the four `SKILL.md` files:

```markdown

## Where this sits in the review flow

See the [review-skills map](../../../wp-labs-standards/skills/change-review/review-skills-map.md):
`change-review` (broad dispatch) → `/code-review` + `/security-review` (deep) →
`requesting-code-review` → `github-pr-prepare` → `receiving-code-review` → `github-pr-review`.
```

Note: the two `wp-labs-standards` skills (`github-pr-review`, `github-pr-prepare`) sit one directory
shallower than the two superpowers skills. Use the relative path that resolves from each file:
- From `wp-labs-standards/skills/<skill>/SKILL.md`: `../change-review/review-skills-map.md`
- From `wp-labs-superpowers/skills/<skill>/SKILL.md`: `../../../wp-labs-standards/skills/change-review/review-skills-map.md`

- [ ] **Step 2: Verify each file got the footer**

Run:
```bash
cd /Users/sherryzhou/code/claude-starter
for f in plugins/wp-labs-standards/skills/github-pr-review/SKILL.md \
         plugins/wp-labs-standards/skills/github-pr-prepare/SKILL.md \
         plugins/wp-labs-superpowers/skills/requesting-code-review/SKILL.md \
         plugins/wp-labs-superpowers/skills/receiving-code-review/SKILL.md; do
  grep -q "Where this sits in the review flow" "$f" && echo "OK $f" || echo "MISSING $f"
done
```
Expected: four `OK` lines.

- [ ] **Step 3: Commit**

```bash
git add plugins/wp-labs-standards/skills/github-pr-review/SKILL.md \
        plugins/wp-labs-standards/skills/github-pr-prepare/SKILL.md \
        plugins/wp-labs-superpowers/skills/requesting-code-review/SKILL.md \
        plugins/wp-labs-superpowers/skills/receiving-code-review/SKILL.md
git commit -m "docs(review): cross-link adjacent skills to the review-skills map"
```

---

### Task 4: Rewrite the CI workflow template

**Files:**
- Modify: `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml`

**Interfaces:**
- Consumes: the `change-review` skill (Task 1) via `plugins: 'wp-labs-standards@wp-labs-starter'`.

- [ ] **Step 1: Replace the workflow with a single change-review job**

Overwrite `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml` with exactly:

```yaml
name: Code Review

on:
  pull_request:
    types: [opened, synchronize, ready_for_review, reopened]

jobs:
  change-review:
    # Skip when the PR opts out of all Claude automation.
    if: ${{ !contains(github.event.pull_request.labels.*.name, 'no-automation') }}
    runs-on: ubuntu-latest
    permissions:
      contents: write        # write so high-confidence --fix lands as an [autofix] commit
      pull-requests: write    # write so findings can be posted as PR comments
      issues: read
      id-token: write
    steps:
      - name: Checkout repository
        uses: actions/checkout@v5
        with:
          # full history so the review can diff the PR against its base and materialize it
          fetch-depth: 0
          ref: ${{ github.event.pull_request.head.ref }}

      - name: Detect autofix commit
        id: detect
        run: |
          SUBJECT="$(git log -1 --pretty=%s)"
          if printf '%s' "$SUBJECT" | grep -q '^\[autofix\]'; then
            echo "skip=true" >> "$GITHUB_OUTPUT"
          else
            echo "skip=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Run change-review (broad checklist + deep correctness + deep security)
        if: steps.detect.outputs.skip == 'false'
        id: change-review
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          plugin_marketplaces: 'https://github.com/cssherry-wp/wp-labs-starter.git'
          plugins: 'wp-labs-standards@wp-labs-starter'
          prompt: |
            /wp-labs-standards:change-review --fix --comment --effort high
            Review the changes in this pull request against its base branch.
            Apply only high-confidence, mechanically-fixable findings; commit them to the PR
            branch as a single commit whose subject begins with "[autofix]" and push it.
            Post every remaining (un-fixable or lower-confidence) finding as a comment on
            PR #${{ github.event.pull_request.number }} in ${{ github.repository }} using
            `gh pr comment`, each annotated with its confidence score. If there are no findings,
            say so briefly in one comment.
          claude_args: '--allowed-tools "Bash,Edit,Read,Grep,Glob,Skill"'
```

- [ ] **Step 2: Verify the YAML parses and the security-review job is gone**

Run:
```bash
cd /Users/sherryzhou/code/claude-starter
python3 -c "import yaml,sys; d=yaml.safe_load(open('plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml')); print('jobs:', list(d['jobs'].keys()))"
grep -c 'security-review' plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml
grep -c 'code-review@claude-code-plugins' plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml
```
Expected: `jobs: ['change-review']`; both `grep -c` print `0`.

- [ ] **Step 3: Commit**

```bash
git add plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml
git commit -m "feat(sdlc): code-review.yml runs change-review as one job"
```

---

### Task 5: Update scaffolding-sdlc doc + marketplace description

**Files:**
- Modify: `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/SKILL.md`
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Note the new behavior in the scaffolding doc**

In `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/SKILL.md` line 56, replace:
```
   - each workflow: `ci.yml`, `security.yml`, `code-review.yml`, `claude.yml`,
```
with:
```
   - each workflow: `ci.yml`, `security.yml`, `code-review.yml` (runs `change-review`:
     broad checklist + deep `/code-review` + deep `/security-review` in one job), `claude.yml`,
```

- [ ] **Step 2: List change-review in the marketplace description**

In `.claude-plugin/marketplace.json`, in the `wp-labs-standards` entry's `description`, replace:
```
plus common-task workflows: /commit, github-pr-prepare, and github-pr-review.
```
with:
```
plus common-task workflows: /commit, change-review (broad review dispatcher), github-pr-prepare, and github-pr-review.
```

- [ ] **Step 3: Verify JSON is still valid**

Run:
```bash
cd /Users/sherryzhou/code/claude-starter
python3 -c "import json; json.load(open('.claude-plugin/marketplace.json')); print('JSON_OK')"
grep -q "change-review" .claude-plugin/marketplace.json && echo DESC_OK
```
Expected: `JSON_OK` and `DESC_OK`.

- [ ] **Step 4: Commit**

```bash
git add plugins/wp-labs-sdlc/skills/scaffolding-sdlc/SKILL.md .claude-plugin/marketplace.json
git commit -m "docs(sdlc): note change-review in scaffolding doc and marketplace"
```

---

### Task 6: Apply the workflow to `translation_sdlc_demo`

**Files:**
- Modify: `/Users/sherryzhou/code/translation_sdlc_demo/.github/workflows/code-review.yml`

**Interfaces:**
- Consumes: the finalized template from Task 4 (this is a copy of it).

- [ ] **Step 1: Confirm it still matches the OLD template (no local drift) before overwriting**

Run:
```bash
git -C /Users/sherryzhou/code/translation_sdlc_demo status --short .github/workflows/code-review.yml
git -C /Users/sherryzhou/code/translation_sdlc_demo branch --show-current
```
Expected: clean (no uncommitted changes to that file). Note the current branch — the edit lands there; the team can open a PR / cherry-pick to the default branch. If the working tree is dirty, stop and ask.

- [ ] **Step 2: Copy the new template over it**

Run:
```bash
cp /Users/sherryzhou/code/claude-starter/plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml \
   /Users/sherryzhou/code/translation_sdlc_demo/.github/workflows/code-review.yml
```

- [ ] **Step 3: Verify it matches the template**

Run:
```bash
diff /Users/sherryzhou/code/claude-starter/plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml \
     /Users/sherryzhou/code/translation_sdlc_demo/.github/workflows/code-review.yml && echo IDENTICAL
```
Expected: `IDENTICAL`.

- [ ] **Step 4: Commit in that repo**

```bash
cd /Users/sherryzhou/code/translation_sdlc_demo
git add .github/workflows/code-review.yml
git commit -m "ci: run change-review (one job, security folded in)"
```

---

## Self-Review

**Spec coverage:**
- Goal 1 (change-review skill, checklist + hand-offs + flags) → Task 1. ✓
- Goal 2 (fold deep correctness + security; remove CI security job) → Task 1 (hand-offs) + Task 4 (job removed). ✓
- Goal 3 (`--fix`/`--comment` across all steps) → Task 1 sections 0, 5, 6. ✓
- Goal 4 (absorb git-history, prior-PR, inline-comment, confidence) → Task 1 sections 2, 3, 5. ✓
- Goal 5 (CI runs change-review) → Task 4, revised to the two-job split (see revision note). ✓
- Goal 6 (review-skills map + collision callout) → Task 2. ✓
- Goal 7 (apply across repos) → Task 6 (`translation_sdlc_demo`); template is source of truth (Task 4). ✓
- Cross-links (Component C) → Task 3. ✓
- Supporting doc/marketplace updates (Component D) → Task 5. ✓

**Placeholder scan:** No TBD/TODO; every code/YAML/markdown step contains full content. Deferred items (`/code-review` diff target) are documented as a caveat in the skill, not left as a plan gap.

**Type consistency:** Skill name `change-review` and invocation `/wp-labs-standards:change-review` are consistent across Tasks 1, 4, 5. Confidence threshold (≥80 for `--fix`) is stated once (section 5) and referenced consistently. Map filename `review-skills-map.md` matches across Tasks 2 and 3.

---

## Revision: Task 4 superseded by a split-job design (security)

After Task 4 was committed (one job), two automated security reviews flagged a CRITICAL
prompt-injection→RCE risk (agent on untrusted PR content + `contents: write` + push in one
job). User approved splitting. The authoritative replacement spec lives in
`.superpowers/sdd/task-4b-brief.md` and was implemented over the one-job version:

- `review` job: runs the agent with `contents: read`, denylists `git push`/`commit`/`gh pr
  comment`, same-repo gated; emits `autofix.patch` + `change-review-findings.md` as an artifact.
- `apply` job: no agent, `contents: write`; `git apply` + `--no-verify` commit + push + `gh
  pr comment`; gated on `needs.review.outputs.skip == 'false'`.
- Marketplace pinned to SHA `d444e09a...`.

Task 6 (translation_sdlc_demo) copies this split template, not the one-job version. Consuming
repos must branch-protect the merge target — see the spec revision note.
