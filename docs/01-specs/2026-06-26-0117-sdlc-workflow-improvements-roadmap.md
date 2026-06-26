# Roadmap (TRACKING): SDLC workflow improvements

**Status:** Tracking doc — captures the full original brainstorming scope so detail isn't lost as
sub-projects are tackled one at a time. Each sub-project gets its own spec→plan→build cycle.
**Date:** 2026-06-26

## Origin

From a single brainstorming request covering six related improvements to the `wp-labs-sdlc` plugin
(and the `change-review` skill in `wp-labs-standards`). The work was decomposed into four
sub-projects and sequenced by the user:

**Order:** (1) Azure deploy → (2) issue/autofix automation → (3) PR/issue templates →
(4) stack-aware gating.

| # | Sub-project | Status | Spec |
|---|---|---|---|
| 1 | Azure Container Apps deploy option | **In progress** | `2026-06-26-0032-azure-container-apps-deploy-option.md` |
| 2 | Issue auto-categorization + code-review-creates-issues + `autofix` | Pending | _this doc → own spec_ |
| 3 | PR template + issue template | Pending | _this doc → own spec_ |
| 4 | Stack-aware workflow gating | Pending | _this doc → own spec_ |
| — | CI restructure + make-consistency (spun off mid-design) | Parked | `2026-06-26-0032-ci-restructure-and-make-consistency.md` |

The detailed requirements below are captured verbatim-in-intent from the original request, to be
refined into real specs when each sub-project is brainstormed.

---

## Sub-project 2 — Issue auto-categorization + code-review → issues + `autofix`

The largest piece, with the most security surface (agentic PR creation from issue descriptions).
Three linked parts:

### 2a. AI issue categorizer (Haiku)

- A workflow/script that runs when a **new issue** is opened.
- Uses **Haiku** to judge whether the issue is **easy to fix**.
- **Skip** any issue whose description contains the marker `<!-- claude-autofix -->` (mirrors the
  existing comment-triage loop-prevention marker).
- Outcome: label the issue accordingly (e.g. an "easy-fix" signal feeding into the
  `Automation suggested` flow below).

### 2b. `change-review` / `code-review.yml` creates issues (not just inline comments)

Update the review flow so findings become **issues**, with this structure:

- **Nits grouped together** into a single issue.
- Findings **needing additional human input** → opened **separately**, labeled **`question`**.
- Every issue includes a **confidence level**.
- Every issue description includes a **superpower implementation plan**.
- **Bugs** are labeled as such.
- If a finding **can be fixed by automation** → assign label **`Automation suggested`**.

### 2c. `autofix` workflow (triggered by `Automation approved`)

- When a human adds the label **`Automation approved`** to an issue, a separate **`autofix`**
  workflow:
  1. Reads the issue description (incl. the superpower implementation plan).
  2. Runs the **forked superpower `executing-plans` skill**, **agentically if possible**.
  3. **Creates a PR** with the fix.
- Security: this is agentic code-gen from issue text — must treat the issue body as untrusted data,
  scope tightly, same-repo only, human-review gate before merge (reuse the `code-review.yml` /
  comment-triage security model and `<!-- claude-autofix -->` loop prevention).

### New labels implied (2)
`Automation suggested`, `Automation approved`, plus whatever the categorizer emits (e.g. `easy-fix`),
`bug`. Reconcile naming/casing with the existing managed label set in `scripts/ensure-labels.sh`.

---

## Sub-project 3 — PR template + issue template

### Issue template
- Propose and follow a standard issue template.
- Fields: **proposed fix**, **impact**, **justification**, **current behavior**, and a **link to the
  originating PR comment**.
- Aligns with the issues that sub-project 2b creates.

### PR template
- Check whether the sdlc already provides a PR template — **it does not today** (only the reference
  `django_app-main` has one). Create one **based on the current/team template**.
- Additions to the template:
  - A flag for whether the change is a **breaking change**.
  - A **"How to test"** section.
  - A note that "How to test" is a good place for **screenshots**.

---

## Sub-project 4 — Stack-aware workflow gating

- **Not all workflows are necessary for every new repo** — customize what the scaffolder copies based
  on the detected **tech stack**.
- Today `scaffolding-sdlc` detects the stack and audits an inventory, but the gating is mostly prose
  guidance. Formalize **which workflows ship for which stack** (e.g. backend-only repos skip Playwright
  e2e; CLI-library stacks skip the hosting layer).
- **Overlaps the parked CI restructure** (`2026-06-26-0032-ci-restructure-and-make-consistency.md`):
  splitting `ci.yml` into per-stack `on.paths` workflow files is itself a scaffold-time gating
  mechanism. Strongly consider **merging the CI restructure into this sub-project**.

---

## Cross-cutting notes

- Several sub-projects add labels — do a single reconciliation pass against
  `scripts/ensure-labels.sh` (naming, color, description) rather than ad-hoc additions.
- The `<!-- claude-autofix -->` marker and same-repo-only + human-review-gate security model recur
  across the comment-triage, code-review, and proposed `autofix` flows — keep them consistent.
