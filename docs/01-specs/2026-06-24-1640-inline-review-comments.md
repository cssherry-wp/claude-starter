# Spec: Inline change-review comments

## Problem

`code-review.yml`'s `apply` job posts the entire `change-review-findings.md` as a
**single** PR conversation comment ("Post findings comment" step). That dumps every
finding — fixed and unfixed, anchorable and not — into one wall of text divorced from
the code it refers to. Reviewers can't see a finding next to the line it's about, can't
tell at a glance which findings were already auto-fixed, and there is no per-finding
thread for a human to reply on.

## Goal

Replace the single comment with **inline review comments anchored to the relevant code**:

- **Fixed findings** (auto-applied to the working tree as the `[autofix]` commit) are
  posted inline carrying the `<!-- claude-autofix -->` tag, and their review threads are
  **auto-resolved** — collapsed but discoverable.
- **Unfixed findings** that map to a changed line are posted inline next to that code,
  with their thread left **open** for a human.
- **Unanchorable findings** (missing test file, an absent doc, a whole-PR architecture
  concern — anything not tied to a changed line) go into the **review summary body**.
- A **human reply** to any of these threads re-enters the existing
  `claude-comment-triage` workflow, unchanged.

## Non-goals

- No change to the read-only/privileged split: the agent still runs **only** in the
  read-only `review` job. The `apply` job stays agent-free and deterministic.
- No change to `claude-comment-triage.yml` (see "Triage interaction" — it already works).
- No change to what findings the reviewer produces, how confidence is scored, or the
  `--fix` threshold. This spec changes **how findings are delivered**, not what they are.

## Approach

Three coordinated changes, plus a verified no-op on triage.

### 1. Findings become a structured artifact (`change-review-findings.json`)

The `change-review` skill (CI mode) and the `review` job prompt stop writing freeform
`change-review-findings.md` and instead write `change-review-findings.json`. The agent
holds the diff, so the agent — not the privileged job — decides which findings can anchor
to a changed line.

Schema:

```json
{
  "reviewed": "PR #123: feat/foo → main",
  "summary": "<markdown: sections 1,2,5,7 prose + verdict>",
  "findings": [
    {
      "id": "f1",
      "checklist": "correctness",
      "path": "src/foo.ts",
      "line": 42,
      "start_line": null,
      "side": "RIGHT",
      "severity": "med",
      "confidence": 85,
      "status": "fixed",
      "body": "<markdown explanation, no marker — the apply job appends the marker for fixed items>"
    }
  ],
  "unanchored": [
    {
      "id": "f9",
      "checklist": "tests",
      "confidence": 70,
      "body": "No test covers the new error path in src/foo.ts",
      "hint": "tests/foo.test.ts (suggested)"
    }
  ]
}
```

Rules the skill must follow:

- A finding goes in `findings[]` **only if** `path` + `line` fall inside the PR diff
  (an inline review comment on a line outside the diff is rejected by GitHub with 422).
  Everything else goes in `unanchored[]`.
- `status: "fixed"` iff the finding was applied to the working tree under `--fix`
  (confidence ≥ 80, mechanically fixable). All others are `"unfixed"`.
- `side: "RIGHT"` for additions/context on the head side; `"LEFT"` for a finding about a
  removed line. `start_line` set only for a multi-line range (else `null`).
- The file is **always** written, even with zero findings (`findings: []`,
  `unanchored: []`) — a missing file still signals "agent did not complete", as today.

The skill's section 6 and section 7 (output format) gain a short note that CI mode emits
this JSON; the human-facing markdown report is unchanged for local/`--comment` use.

### 2. New `github-pr-review` recipe: create a review with inline comments

The `github-pr-review` skill currently documents only **reply** and **resolve**. Add a
**"Create a review with inline comments"** recipe so the skill remains the single source
of truth for the posting plumbing. It is plain `gh api` — no LLM:

- REST: `POST /repos/{owner}/{repo}/pulls/{n}/reviews` with
  `{ commit_id, body, event: "COMMENT", comments: [{ path, line, side, body }, ...] }`.
- Note the constraints: every comment's `line`/`side` must be within the diff of
  `commit_id`; `commit_id` must be a commit in the PR; one call fires exactly one
  `pull_request_review` event.
- Document building the payload deterministically from a JSON file with `jq` and
  submitting via `gh api --input`.

Also add a **"Resolve threads whose seed comment matches a marker"** helper (query
`reviewThreads`, filter where `comments.nodes[0].body` contains the marker, then
`resolveReviewThread` each) — this reuses the existing resolve mutation.

### 3. `apply` job rebuilds posting from the JSON (deterministic bash)

Replace the single "Post findings comment" step. The agent does **not** run here; bash +
`jq` + `gh api` consume the JSON the read-only job produced. **Order is critical:**

1. **Post one PR review** against the **reviewed head SHA**
   (`${{ github.event.pull_request.head.sha }}` — the exact commit the agent reviewed),
   built per the new recipe:
   - Each `findings[]` item → one inline comment `{path, line, side, body}`. For
     `status:"fixed"`, the comment `body` gets the `<!-- claude-autofix -->` marker
     appended and a "auto-fixed in this PR" note; confidence is shown on every comment.
   - Review `body` = `summary` + an **"Auto-fixed (N)"** list + the **`unanchored[]`**
     findings + a trailing `<!-- claude-autofix -->` marker.
   - `event: "COMMENT"`.
2. **Resolve the fixed threads** via the marker helper: resolve every review thread whose
   seed comment contains `<!-- claude-autofix -->`. (Only fixed findings carry it in their
   per-comment body; unfixed comments don't, so they stay open.)
3. **Then** apply + push the autofix patch (the existing "Apply autofix patch and push"
   step moves to run *after* posting).

Why this order: posting before the push anchors inline comments to the SHA the agent
actually reviewed, so line numbers match. The subsequent push only marks the fixed
threads "outdated" (they're already resolved). The push's `synchronize` re-run is already
suppressed by the `[autofix]` detect step in the `review` job.

If `change-review-findings.json` is missing/empty: post a review with body
`"⚠️ change-review did not produce findings — agent may not have completed"` + the marker,
mirroring today's missing-file warning. Step-summary lines (counts of inline / auto-fixed
/ unanchored / resolved) replace today's "findings comment: posted" line.

Permissions already present on `apply` (`pull-requests: write`, `contents: write`) cover
submitting reviews and resolving threads. No new permissions.

### Triage interaction (no change needed — verified)

- The review in step 1 is authored by `GITHUB_TOKEN`. GitHub does **not** trigger
  workflows from `GITHUB_TOKEN`-authored events, so the posting never self-triggers
  triage. The `<!-- claude-autofix -->` marker in the review body is belt-and-suspenders
  (covers the case of a human PAT) — triage's `pull_request_review` branch skips bodies
  containing it.
- A **human reply** to any inline thread fires `pull_request_review_comment.created` from
  a trusted author with no marker and no `@claude` → `claude-comment-triage.yml`'s second
  `if` branch already matches it. No edit to the triage workflow.

## Components

| Unit | File | Responsibility |
|---|---|---|
| Findings producer | `change-review/SKILL.md` (+ `review` job prompt in `code-review.yml`) | Emit `change-review-findings.json` split into anchorable / unanchorable / fixed |
| Posting plumbing | `github-pr-review/SKILL.md` | Document `create review with inline comments` + `resolve-by-marker` (plain `gh api`) |
| Deterministic poster | `apply` job in `code-review.yml` | Build review from JSON, post, resolve fixed threads, then push autofix |
| Triage | `claude-comment-triage.yml` | Unchanged; consumes human replies to the new threads |

## Testing

Workflow YAML and skills aren't unit-testable here, so verification is staged:

1. **Payload builder (unit-ish):** the `jq` transform from a sample
   `change-review-findings.json` → the `reviews` API payload is exercised against
   fixture JSON (zero findings, only-unanchored, fixed+unfixed mix, multi-line range) and
   the output asserted (valid JSON, markers only on fixed, unanchored in body). Run as a
   shell check, not via the live API.
2. **End-to-end on a throwaway PR:** open a PR with a seeded lint/style issue + a
   missing-test gap, confirm: one review posted, fixed finding inline + tagged + thread
   resolved, unfixed finding inline + thread open, missing-test in the summary body,
   `[autofix]` commit pushed, and the `[autofix]` re-run skipped.
3. **Triage round-trip:** reply to the open unfixed thread as a trusted user, confirm
   `claude-comment-triage` triggers and the autofix-tagged threads are ignored (marker).

## Risks / open questions

- **Line drift between review and reviewed SHA:** mitigated by anchoring to
  `head.sha` and posting before the autofix push. If the agent's `line` is still stale
  (e.g. it reasoned about a post-fix tree), GitHub returns 422 for that comment — the
  builder should skip a rejected comment and fold it into the summary body rather than
  failing the whole review. (Builder must tolerate partial rejection.)
- **`jq` payload construction** is the most error-prone part; fixture tests above guard it.
- The `change-review-findings.md` → `.json` swap is a breaking change to the artifact
  contract, but both producer and consumer are in this same change, so there's no external
  dependency to migrate.
