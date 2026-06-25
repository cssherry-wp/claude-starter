# Inline change-review comments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `code-review.yml`'s single findings comment with inline PR review comments — fixed findings tagged + auto-resolved, unfixed inline + open, unanchorable in the review body — so a human reply re-enters `claude-comment-triage`.

**Architecture:** The read-only `review` job emits findings as structured JSON (`change-review-findings.json`). The privileged, agent-free `apply` job transforms that JSON into one `POST /pulls/{n}/reviews` payload via a co-located `build-review-payload.jq` filter, posts it against the reviewed SHA, resolves the fixed threads via GraphQL, then pushes the autofix patch. `github-pr-review` documents the posting recipes; `claude-comment-triage.yml` is unchanged.

**Tech Stack:** GitHub Actions YAML, bash, `jq`, `gh` CLI (REST + GraphQL), Claude Code skills (Markdown).

## Global Constraints

- Loop-prevention marker is the exact string `<!-- claude-autofix -->` (copied verbatim from `claude-comment-triage.yml`). Every auto-posted *review body* carries it; every *fixed-finding inline comment* carries it. Unfixed inline comments do not.
- The agent runs **only** in the read-only `review` job. The `apply` job stays agent-free (bash/`jq`/`gh` only) — do not add a `claude-code-action` step to it.
- Autofix commit subject begins exactly `[autofix] ` (the `review` job's detect step skips re-runs on it).
- Inline comments are anchored to `${{ github.event.pull_request.head.sha }}` (the reviewed SHA), and the review is posted **before** the autofix patch is pushed.
- These workflow files are **templates** scaffolded into other repos: any runtime helper must live under `templates/github/workflows/` and be copied by `scaffolding-sdlc`.
- Findings artifact is `change-review-findings.json` (replaces `change-review-findings.md`); it is always written, even when empty (`{"findings":[],"unanchored":[]}`). A missing file still means "agent did not complete."

## File Structure

| Action | Path | Responsibility |
|---|---|---|
| Create | `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/build-review-payload.jq` | Pure transform: findings JSON → reviews-API request body. The one logic-heavy, unit-tested unit. |
| Create | `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/tests/build-review-payload.test.sh` + `tests/fixtures/*.json` | Fixture tests for the jq filter (not scaffolded). |
| Modify | `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml` | `review` job emits JSON; `apply` job posts inline review, resolves fixed threads, pushes after. |
| Modify | `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/SKILL.md` | Copy the `.jq` helper alongside the workflow. |
| Modify | `plugins/wp-labs-standards/skills/change-review/SKILL.md` | Document the CI-mode findings JSON schema. |
| Modify | `plugins/wp-labs-standards/skills/github-pr-review/SKILL.md` | Add "create review with inline comments" + "resolve threads by marker" recipes. |

All work is on branch `fix/workflow-logging` (worktree `.claude/worktrees/workflow-logging`). Run all commands from the worktree root.

---

### Task 1: `build-review-payload.jq` filter + fixture tests

The deterministic core. TDD: fixtures first, then the filter.

**Files:**
- Create: `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/build-review-payload.jq`
- Create: `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/tests/build-review-payload.test.sh`
- Create: `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/tests/fixtures/empty.input.json`, `empty.expected.json`, `mixed.input.json`, `mixed.expected.json`, `multiline.input.json`, `multiline.expected.json`

**Interfaces:**
- Consumes: a findings JSON object `{reviewed, summary, findings[], unanchored[]}` on stdin; `--arg commit_id <sha>`; `--arg marker "<!-- claude-autofix -->"`.
  - `findings[]` item: `{id, checklist, path, line, start_line|null, side, severity, confidence, status:"fixed"|"unfixed", body}`.
  - `unanchored[]` item: `{id, checklist, confidence, body, hint?}`.
- Produces: a JSON object suitable for `gh api -X POST .../pulls/{n}/reviews --input -`: `{commit_id, event:"COMMENT", comments:[{path,line,side,body,(start_line,start_side)}], body}`.

- [ ] **Step 1: Write the fixtures (failing inputs + expected outputs)**

Create `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/tests/fixtures/empty.input.json`:

```json
{ "reviewed": "PR #1: feat/x → main", "summary": "No issues found.", "findings": [], "unanchored": [] }
```

Create `tests/fixtures/empty.expected.json`:

```json
{ "commit_id": "deadbeef", "event": "COMMENT", "comments": [], "body": "No issues found.\n\n<!-- claude-autofix -->" }
```

Create `tests/fixtures/mixed.input.json`:

```json
{
  "reviewed": "PR #2: feat/y → main",
  "summary": "### Summary\nAdds a parser.",
  "findings": [
    { "id": "f1", "checklist": "lint", "path": "src/a.ts", "line": 10, "start_line": null, "side": "RIGHT", "severity": "low", "confidence": 90, "status": "fixed", "body": "Unused import removed." },
    { "id": "f2", "checklist": "correctness", "path": "src/b.ts", "line": 22, "start_line": null, "side": "RIGHT", "severity": "med", "confidence": 65, "status": "unfixed", "body": "Possible null deref on `cfg`." }
  ],
  "unanchored": [
    { "id": "f3", "checklist": "tests", "confidence": 70, "body": "No test covers the new error path.", "hint": "tests/b.test.ts (suggested)" }
  ]
}
```

Create `tests/fixtures/mixed.expected.json`:

```json
{
  "commit_id": "deadbeef",
  "event": "COMMENT",
  "comments": [
    { "path": "src/a.ts", "line": 10, "side": "RIGHT", "body": "Unused import removed.\n\n_(confidence 90)_\n\n_Auto-fixed in the `[autofix]` commit._\n\n<!-- claude-autofix -->" },
    { "path": "src/b.ts", "line": 22, "side": "RIGHT", "body": "Possible null deref on `cfg`.\n\n_(confidence 65)_" }
  ],
  "body": "### Summary\nAdds a parser.\n\n## Auto-fixed (1)\n- `src/a.ts:10` — Unused import removed.\n\n## Other findings (not line-anchored)\n- No test covers the new error path. _(confidence 70)_ — _tests/b.test.ts (suggested)_\n\n<!-- claude-autofix -->"
}
```

Create `tests/fixtures/multiline.input.json`:

```json
{
  "reviewed": "PR #3", "summary": "S",
  "findings": [
    { "id": "f1", "checklist": "correctness", "path": "src/c.ts", "line": 30, "start_line": 28, "side": "RIGHT", "severity": "high", "confidence": 85, "status": "unfixed", "body": "Range issue." }
  ],
  "unanchored": []
}
```

Create `tests/fixtures/multiline.expected.json`:

```json
{
  "commit_id": "deadbeef", "event": "COMMENT",
  "comments": [
    { "path": "src/c.ts", "line": 30, "side": "RIGHT", "body": "Range issue.\n\n_(confidence 85)_", "start_line": 28, "start_side": "RIGHT" }
  ],
  "body": "S\n\n<!-- claude-autofix -->"
}
```

- [ ] **Step 2: Write the test runner**

Create `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/tests/build-review-payload.test.sh`:

```bash
#!/usr/bin/env bash
# Unit tests for build-review-payload.jq — runs the filter against fixtures and
# compares normalized JSON. Requires: jq. Run: bash tests/build-review-payload.test.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
JQ_FILE="$HERE/../templates/github/workflows/build-review-payload.jq"
MARKER='<!-- claude-autofix -->'
fail=0

run_case() {
  local name="$1" got want
  got="$(jq -f "$JQ_FILE" --arg commit_id "deadbeef" --arg marker "$MARKER" \
        "$HERE/fixtures/$name.input.json" | jq -S .)"
  want="$(jq -S . "$HERE/fixtures/$name.expected.json")"
  if [ "$got" = "$want" ]; then
    echo "PASS: $name"
  else
    echo "FAIL: $name"; diff <(printf '%s\n' "$want") <(printf '%s\n' "$got") || true; fail=1
  fi
}

run_case empty
run_case mixed
run_case multiline
exit "$fail"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `bash plugins/wp-labs-sdlc/skills/scaffolding-sdlc/tests/build-review-payload.test.sh`
Expected: FAIL — `jq: error: Could not open "build-review-payload.jq"` (filter not created yet), non-zero exit.

- [ ] **Step 4: Write the jq filter**

Create `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/build-review-payload.jq`:

```jq
# Transform change-review-findings.json into a GitHub "create review" request body.
# Args: --arg commit_id <reviewed head sha>   --arg marker "<!-- claude-autofix -->"
# Output: { commit_id, event:"COMMENT", comments:[...], body } for
#   gh api -X POST /repos/{owner}/{repo}/pulls/{n}/reviews --input -
# Only findings[] (line-anchored) become inline comments; unanchored[] + an
# auto-fixed digest go into the review body. Fixed findings carry the marker.

def confidence_line: "\n\n_(confidence \(.confidence))_";

def comment_body:
  .body + confidence_line
  + (if .status == "fixed"
     then "\n\n_Auto-fixed in the `[autofix]` commit._\n\n" + $marker
     else "" end);

def inline_comment:
  { path: .path, line: .line, side: (.side // "RIGHT"), body: comment_body }
  + (if .start_line != null
     then { start_line: .start_line, start_side: (.side // "RIGHT") }
     else {} end);

def fixed_list:
  [ (.findings // [])[] | select(.status == "fixed")
    | "- `\(.path):\(.line)` — \(.body | split("\n")[0])" ];

def unanchored_list:
  [ (.unanchored // [])[]
    | "- \(.body) _(confidence \(.confidence))_"
      + (if .hint then " — _\(.hint)_" else "" end) ];

{
  commit_id: $commit_id,
  event: "COMMENT",
  comments: [ (.findings // [])[] | inline_comment ],
  body: (
    (.summary // "")
    + (if (fixed_list | length) > 0
       then "\n\n## Auto-fixed (\(fixed_list | length))\n" + (fixed_list | join("\n"))
       else "" end)
    + (if (unanchored_list | length) > 0
       then "\n\n## Other findings (not line-anchored)\n" + (unanchored_list | join("\n"))
       else "" end)
    + "\n\n" + $marker
  )
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `bash plugins/wp-labs-sdlc/skills/scaffolding-sdlc/tests/build-review-payload.test.sh`
Expected: `PASS: empty` / `PASS: mixed` / `PASS: multiline`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/build-review-payload.jq \
        plugins/wp-labs-sdlc/skills/scaffolding-sdlc/tests/
git commit -m "feat(sdlc): add build-review-payload.jq + fixture tests"
```

---

### Task 2: Add posting recipes to `github-pr-review` skill

Document the two new plumbing recipes so the skill is the single source of truth. Pure `gh api`.

**Files:**
- Modify: `plugins/wp-labs-standards/skills/github-pr-review/SKILL.md`

**Interfaces:**
- Consumes: nothing (documentation).
- Produces: the canonical `gh api` REST/GraphQL commands the `apply` job (Task 4) mirrors.

- [ ] **Step 1: Add the two recipes after the "Batch Operations" section**

Insert this block before the `## Complete Example` section in `github-pr-review/SKILL.md`:

````markdown
## Create a Review with Inline Comments

Post many inline comments in **one** review (one `pull_request_review` event). Pure
`gh api` — no LLM. Build the payload from a JSON file and submit it:

```bash
# payload.json: { "commit_id": "...", "event": "COMMENT", "body": "...",
#                 "comments": [ { "path": "...", "line": N, "side": "RIGHT", "body": "..." } ] }
gh api -X POST "repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews" --input payload.json
```

Constraints:
- Each comment's `line`/`side` MUST fall inside the diff of `commit_id`, and `commit_id`
  MUST be a commit in the PR — otherwise GitHub rejects the **whole call** with 422.
  (The reviews API is all-or-nothing; it cannot skip one bad comment.) On 422, re-submit
  with an empty `comments` array and fold the findings into `body`.
- Multi-line range: add `start_line` + `start_side` to a comment.
- `event: "COMMENT"` posts without approving/requesting-changes.

## Resolve Threads Whose Seed Comment Matches a Marker

Resolve every review thread whose first comment contains a marker (e.g. auto-fixed
findings tagged `<!-- claude-autofix -->`):

```bash
MARKER='<!-- claude-autofix -->'
gh api graphql -f query="
query {
  repository(owner: \"$OWNER\", name: \"$REPO\") {
    pullRequest(number: $PR_NUMBER) {
      reviewThreads(first: 100) {
        nodes { id isResolved comments(first: 1) { nodes { body } } }
      }
    }
  }
}" | jq -r --arg m "$MARKER" \
  '.data.repository.pullRequest.reviewThreads.nodes[]
   | select(.isResolved | not)
   | select(.comments.nodes[0].body | contains($m)) | .id' \
| while read -r tid; do
    gh api graphql -f query="
mutation { resolveReviewThread(input: { threadId: \"$tid\" }) { thread { id isResolved } } }"
  done
```
````

- [ ] **Step 2: Verify the embedded snippets are syntactically valid**

Run: `jq -n 'def x: "ok"; x'` (sanity that local `jq` works), then visually confirm the
jq filter in the resolve recipe parses:

Run: `echo '{"data":{"repository":{"pullRequest":{"reviewThreads":{"nodes":[]}}}}}' | jq -r --arg m "X" '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved | not) | select(.comments.nodes[0].body | contains($m)) | .id'`
Expected: no output, exit 0 (valid filter, empty result).

- [ ] **Step 3: Commit**

```bash
git add plugins/wp-labs-standards/skills/github-pr-review/SKILL.md
git commit -m "docs(github-pr-review): add inline-review + resolve-by-marker recipes"
```

---

### Task 3: Document the findings JSON schema in `change-review`

**Files:**
- Modify: `plugins/wp-labs-standards/skills/change-review/SKILL.md`

**Interfaces:**
- Consumes: nothing (documentation).
- Produces: the schema contract the `review` job prompt (Task 4) instructs the agent to emit, and Task 1's filter consumes.

- [ ] **Step 1: Update the `--comment` bullet in section 6**

In `change-review/SKILL.md`, find the `--comment` bullet under `## 6. Apply / comment` ending with:

```
  **In CI the agent instead writes all findings (with scores) to `change-review-findings.md`, and
  the separate privileged job posts that file as the PR comment.**
```

Replace that sentence with:

```
  **In CI the agent instead writes all findings to `change-review-findings.json` (schema below);
  the separate privileged job turns each line-anchored finding into an inline review comment and
  posts the rest in the review body.**
```

- [ ] **Step 2: Add the schema subsection at the end of section 6**

Append to section 6 of `change-review/SKILL.md`:

````markdown
### CI findings JSON (`change-review-findings.json`)

When run from CI (read-only mode, `--fix --comment`), write findings as JSON, not prose.
Decide anchoring yourself — you hold the diff:

- A finding goes in `findings[]` **only if** its `path` + `line` fall inside the PR diff
  (an inline comment on a line outside the diff is rejected). Everything else (missing test,
  absent doc, whole-PR concern) goes in `unanchored[]`.
- `status: "fixed"` iff you applied the fix to the working tree under `--fix` (confidence ≥ 80,
  mechanically fixable). All other findings are `"unfixed"`.
- `side`: `"RIGHT"` for head-side/added/context lines, `"LEFT"` for a removed line. Set
  `start_line` only for a multi-line range, else `null`.
- Always write the file, even with no findings (`{"findings":[],"unanchored":[]}`).

```json
{
  "reviewed": "PR #123: feat/foo → main",
  "summary": "<markdown: sections 1,2,5,7 prose + verdict>",
  "findings": [
    { "id": "f1", "checklist": "correctness", "path": "src/foo.ts", "line": 42,
      "start_line": null, "side": "RIGHT", "severity": "med", "confidence": 85,
      "status": "fixed", "body": "<markdown; do NOT add the marker — the job appends it for fixed items>" }
  ],
  "unanchored": [
    { "id": "f9", "checklist": "tests", "confidence": 70,
      "body": "No test covers the new error path", "hint": "tests/foo.test.ts (suggested)" }
  ]
}
```
````

- [ ] **Step 3: Verify the embedded JSON sample parses**

Run: `sed -n '/^```json$/,/^```$/p' plugins/wp-labs-standards/skills/change-review/SKILL.md | grep -v '^```' | jq empty`
Expected: exit 0 for the schema sample (no parse error). If multiple JSON blocks exist, confirm the new one is valid by isolating it; a parse error means fix the sample.

- [ ] **Step 4: Commit**

```bash
git add plugins/wp-labs-standards/skills/change-review/SKILL.md
git commit -m "docs(change-review): define CI findings JSON schema"
```

---

### Task 4: `code-review.yml` — `review` job emits JSON, `apply` job posts inline

The producer + consumer change, in one file, sharing the JSON contract.

**Files:**
- Modify: `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml`

**Interfaces:**
- Consumes: `build-review-payload.jq` (Task 1) at runtime path `.github/workflows/build-review-payload.jq`; the JSON schema (Task 3); the recipes (Task 2).
- Produces: an artifact containing `change-review-findings.json` + `autofix.patch`; posts one PR review + resolves fixed threads + pushes `[autofix]`.

- [ ] **Step 1: Update the `review` job prompt to emit JSON**

In `code-review.yml`, replace the `prompt:` block of the "Run change-review" step:

```yaml
          prompt: |
            /wp-labs-standards:change-review --fix --effort high
            Review the changes in this pull request against its base branch.
            Apply ONLY high-confidence, mechanically-fixable findings to the working tree.
            Do NOT commit, push, or post any PR comment. Write every finding (each with
            its confidence score), including ones you did not fix, to the file
            change-review-findings.md in the repository root.
```

with:

```yaml
          prompt: |
            /wp-labs-standards:change-review --fix --comment --effort high
            Review the changes in this pull request against its base branch.
            Apply ONLY high-confidence, mechanically-fixable findings to the working tree.
            Do NOT commit, push, or post any PR comment. Write ALL findings to
            change-review-findings.json in the repository root, following the CI findings
            JSON schema in the change-review skill: line-anchored findings (path+line inside
            the diff) go in findings[] with status "fixed" or "unfixed"; everything else goes
            in unanchored[]. Always write the file, even if there are no findings.
```

- [ ] **Step 2: Update the "Package patch and findings" step to handle JSON**

In `code-review.yml`, replace the `change-review-findings.md` handling inside the
"Package patch and findings" step:

```yaml
          if [ -f change-review-findings.md ]; then
            BYTES=$(wc -c < change-review-findings.md | tr -d ' ')
            mv change-review-findings.md "$OUT/change-review-findings.md"
            echo "- findings file: present (${BYTES} bytes)" >> "$GITHUB_STEP_SUMMARY"
          else
            echo "::warning::change-review-findings.md was not produced — the agent may not have completed; check the 'Run change-review' step log."
            echo "⚠️ change-review did not produce a findings file — the agent may not have completed. Check the workflow run log." > "$OUT/change-review-findings.md"
            echo "- findings file: **MISSING** (agent may not have completed)" >> "$GITHUB_STEP_SUMMARY"
          fi
```

with:

```yaml
          if [ -f change-review-findings.json ] && jq empty change-review-findings.json 2>/dev/null; then
            COUNT=$(jq '(.findings | length) + (.unanchored | length)' change-review-findings.json)
            mv change-review-findings.json "$OUT/change-review-findings.json"
            echo "- findings file: present (${COUNT} finding(s))" >> "$GITHUB_STEP_SUMMARY"
          else
            echo "::warning::change-review-findings.json missing or invalid — the agent may not have completed; check the 'Run change-review' step log."
            printf '{"reviewed":"","summary":"⚠️ change-review did not produce a valid findings file — the agent may not have completed. Check the workflow run log.","findings":[],"unanchored":[]}' > "$OUT/change-review-findings.json"
            echo "- findings file: **MISSING/INVALID** (agent may not have completed)" >> "$GITHUB_STEP_SUMMARY"
          fi
```

- [ ] **Step 3: Reorder the `apply` job and replace the comment step**

In `code-review.yml`, in the `apply` job, **move the "Apply autofix patch and push" step to
run AFTER posting** and **replace the "Post findings comment" step** with a post-review step
followed by the existing apply-and-push step. The `apply` job's steps become, in order:
Checkout → Download artifact → **Post inline review + resolve fixed threads** → **Apply autofix patch and push**.

Replace the "Post findings comment" step with this new step (placed BEFORE "Apply autofix patch and push"):

```yaml
      - name: Post inline review and resolve fixed threads
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          MARKER: '<!-- claude-autofix -->'
          COMMIT_ID: ${{ github.event.pull_request.head.sha }}
          PR: ${{ github.event.pull_request.number }}
          REPO: ${{ github.repository }}
        run: |
          set -euo pipefail
          FINDINGS="cr/change-review-findings.json"
          if [ ! -s "$FINDINGS" ]; then
            echo "::warning::no findings file to post."
            echo "- review: NOT posted (empty/missing findings file)" >> "$GITHUB_STEP_SUMMARY"
            exit 0
          fi
          # Build the reviews-API payload deterministically (no agent). The .jq helper is
          # scaffolded next to this workflow, so it is present after checkout.
          jq -f .github/workflows/build-review-payload.jq \
             --arg commit_id "$COMMIT_ID" --arg marker "$MARKER" \
             "$FINDINGS" > payload.json

          # One review = one pull_request_review event (skipped by triage via the marker
          # in the body). The reviews API is all-or-nothing: if any inline line is outside
          # the diff it 422s, so fall back to a body-only review.
          if gh api -X POST "repos/$REPO/pulls/$PR/reviews" --input payload.json >/dev/null 2>posterr; then
            echo "::notice::posted inline review to PR #$PR"
            echo "- review: posted with $(jq '.comments | length' payload.json) inline comment(s)" >> "$GITHUB_STEP_SUMMARY"
          else
            echo "::warning::inline review rejected ($(cat posterr | head -1)); retrying body-only."
            jq '.comments = []' payload.json > payload-body.json
            gh api -X POST "repos/$REPO/pulls/$PR/reviews" --input payload-body.json >/dev/null
            echo "- review: posted body-only (inline comments rejected — likely a line outside the diff)" >> "$GITHUB_STEP_SUMMARY"
          fi

          # Resolve threads whose seed comment carries the marker (the auto-fixed findings).
          OWNER="${REPO%/*}"; NAME="${REPO#*/}"
          gh api graphql -f query="
          query {
            repository(owner: \"$OWNER\", name: \"$NAME\") {
              pullRequest(number: $PR) {
                reviewThreads(first: 100) {
                  nodes { id isResolved comments(first: 1) { nodes { body } } }
                }
              }
            }
          }" | jq -r --arg m "$MARKER" \
            '.data.repository.pullRequest.reviewThreads.nodes[]
             | select(.isResolved | not)
             | select(.comments.nodes[0].body | contains($m)) | .id' \
          | while read -r tid; do
              [ -n "$tid" ] || continue
              gh api graphql -f query="mutation { resolveReviewThread(input: { threadId: \"$tid\" }) { thread { isResolved } } }" >/dev/null
              echo "- resolved auto-fixed thread $tid" >> "$GITHUB_STEP_SUMMARY"
            done
```

Then ensure the existing "Apply autofix patch and push" step appears **after** this new step (cut it from its current position above the old comment step and paste it below the new step). Its body is unchanged.

- [ ] **Step 4: Validate the workflow YAML parses**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open('plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml')); print('ok')"`
Expected: `ok` (no YAML error). If `actionlint` is installed, also run `actionlint plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml` and fix any reported issues.

- [ ] **Step 5: Confirm the jq helper is referenced by the runtime path it will be scaffolded to**

Run: `grep -n "build-review-payload.jq" plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml`
Expected: one match referencing `.github/workflows/build-review-payload.jq` (the scaffolded location, confirmed in Task 5).

- [ ] **Step 6: Commit**

```bash
git add plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml
git commit -m "feat(sdlc): post change-review findings as inline PR comments"
```

---

### Task 5: Scaffold the `.jq` helper alongside the workflow

The workflow now depends on `build-review-payload.jq` at runtime; `scaffolding-sdlc` must copy it.

**Files:**
- Modify: `plugins/wp-labs-sdlc/skills/scaffolding-sdlc/SKILL.md`

**Interfaces:**
- Consumes: nothing.
- Produces: the scaffolding instruction that places `build-review-payload.jq` in target repos' `.github/workflows/`.

- [ ] **Step 1: Update the GitHub Actions copy step**

In `scaffolding-sdlc/SKILL.md`, find step 5 ("GitHub Actions") which currently reads:

```
5. **GitHub Actions.** Copy `templates/github/workflows/*.yml` →
   `.github/workflows/` (gates `ci.yml`/`security.yml`, the Claude automation
```

Change the glob and add a note so the helper travels with `code-review.yml`:

```
5. **GitHub Actions.** Copy `templates/github/workflows/*.yml` →
   `.github/workflows/` (gates `ci.yml`/`security.yml`, the Claude automation
```
becomes — update the first sentence to:
```
5. **GitHub Actions.** Copy `templates/github/workflows/*.yml` →
   `.github/workflows/`. When `code-review.yml` is included, also copy its helper
   `templates/github/workflows/build-review-payload.jq` → `.github/workflows/`
   (the apply job calls it via `jq -f .github/workflows/build-review-payload.jq`). (gates
   `ci.yml`/`security.yml`, the Claude automation
```

(Keep the remainder of the bullet — the dependabot copy and opt-out notes — intact.)

- [ ] **Step 2: Verify both files exist in the template dir**

Run: `ls plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml plugins/wp-labs-sdlc/skills/scaffolding-sdlc/templates/github/workflows/build-review-payload.jq`
Expected: both paths listed, no error.

- [ ] **Step 3: Commit**

```bash
git add plugins/wp-labs-sdlc/skills/scaffolding-sdlc/SKILL.md
git commit -m "docs(sdlc): scaffold build-review-payload.jq with code-review.yml"
```

---

### Task 6: Integration verification (manual, post-merge)

The jq core is unit-tested (Task 1); the workflow itself can only be verified live. Run this
once on a throwaway PR in a repo scaffolded from this branch (or this repo if it carries the
workflow). This task has no code — it is a manual checklist confirming the end-to-end behavior.

- [ ] **Step 1: Seed a PR with a fixable + an unfixable + an unanchorable issue**

Open a PR that introduces (a) an obvious lint/style issue on a changed line (fixable),
(b) a possible-null-deref on a changed line (unfixed, lower confidence), and (c) a new
function with no test (unanchorable). Wait for `Code Review` to run.

- [ ] **Step 2: Confirm review delivery**

Verify on the PR: exactly **one** review posted; the fixable finding appears inline **and**
its thread is **resolved** and its comment ends with `<!-- claude-autofix -->`; the unfixed
finding appears inline with its thread **open**; the missing-test finding appears in the
review **body** under "Other findings"; the review body ends with `<!-- claude-autofix -->`.

- [ ] **Step 3: Confirm autofix push + no re-review loop**

Verify an `[autofix] ...` commit was pushed to the PR branch, and the `synchronize` re-run of
`Code Review` it triggers is **skipped** (the detect step sets `skip=true`).

- [ ] **Step 4: Confirm triage round-trip**

As a trusted user (OWNER/MEMBER/COLLABORATOR), reply to the **open** unfixed thread.
Verify `Claude Comment Triage` triggers on that reply and does **not** trigger on the
auto-fixed (marker-bearing) threads.

- [ ] **Step 5: Record the result**

Note pass/fail of Steps 2–4 in the PR description or a comment. No commit.

---

## Self-Review

**Spec coverage:**
- Inline comments anchored to code → Task 4 (post-review step) + Task 1 (payload). ✓
- Fixed → tagged + auto-resolved → Task 4 (marker in comment body via Task 1 filter; resolve loop). ✓
- Unfixed → inline + open → Task 1 filter (no marker on unfixed) + Task 4 (resolve only marker threads). ✓
- Unanchorable → review body → Task 1 filter (`unanchored_list`). ✓
- Human reply re-enters triage; triage unchanged → Task 6 Step 4 verifies; no triage task (by design). ✓
- Structured JSON artifact → Task 3 (schema) + Task 4 (producer/packaging). ✓
- New github-pr-review recipe → Task 2. ✓
- Agent-free apply job preserved → Task 4 uses bash/jq/gh only (Global Constraint). ✓
- Post before push, anchor to reviewed SHA → Task 4 Step 3 ordering + `COMMIT_ID`. ✓
- 422 graceful degradation → Task 4 body-only fallback (refines spec's per-comment phrasing: the all-or-nothing reviews API forces body-only fallback rather than dropping one comment — documented in Task 2 recipe). ✓
- Scaffolding distributes the helper → Task 5. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full content. ✓

**Type consistency:** `build-review-payload.jq` arg names (`commit_id`, `marker`), input keys (`findings`/`unanchored`/`summary`/`status`/`start_line`/`side`/`hint`/`confidence`), and output keys (`commit_id`/`event`/`comments`/`body`/`start_side`) match across Task 1 (filter + fixtures), Task 3 (schema), and Task 4 (prompt + invocation). The marker string `<!-- claude-autofix -->` is identical everywhere. ✓
