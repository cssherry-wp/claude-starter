# Spec (TRACKING — revisit later): CI restructure + make-consistency

**Status:** Parked — captured from brainstorming, NOT yet finalized or approved.
**Date:** 2026-06-26
**Origin:** Surfaced while designing the Azure deploy sub-project (see
`2026-06-26-0032-azure-container-apps-deploy-option.md`). Deliberately split out to keep the Azure
spec tightly scoped. Revisit as its own spec→plan→build cycle.

## Two problems to fix

### A. CI bypasses `make` in some jobs (make-consistency)

Core plugin principle is **local == CI (both call the same Make targets)**, but `ci.yml` only
half-honors it:

- `python` job → `make check-python` / `typecheck-python` / `test-python` ✅
- root `node` job → `make lint` / `typecheck` / `test` ✅
- **`frontend` job → `npm run lint` / `typecheck` / `npm test`** ❌ bypasses make
- **`e2e` job → `npx playwright test`** ❌ bypasses make (a `test-e2e` target exists, unused)

Fix: every CI job calls a Make target; the Makefile stays the single source of truth. The granular
targets already exist (`lint-js`, `check-js`, `test-e2e`, etc.).

### B. Monolithic `ci.yml` runs (and skips) all stacks (speed + cleanliness)

Today `ci.yml` is one file with detect-and-skip jobs for `node` / `frontend` / `python` / `e2e`.
Downsides: jobs run/skip at runtime even when irrelevant; a single-stack repo still carries jobs for
stacks it doesn't have.

There are **two distinct goals** that were being conflated:

| Goal | Mechanism | Notes |
|---|---|---|
| **Run-time:** in a fullstack repo, skip Python work when only frontend changed | paths-filter job (1 file) **or** `on.paths` (N files) | speed |
| **Scaffold-time:** a TS-only repo never even *gets* a Python job | scaffolder copies only relevant workflow files | overlaps **sub-project 4 (stack-aware gating)** |

## Options considered

1. **Single `ci.yml` + leading `changes` job** (e.g. `dorny/paths-filter`) emitting outputs; each job
   gated with `if: needs.changes.outputs.<area> == 'true'`. The Makefile exposes granular targets;
   the workflow decides which to invoke. One file, parallel jobs.
   - **Caveat:** a skipped job still shows in the checks UI, and a skipped **required** check can
     *block* the PR (GitHub's "skipped required check" problem). Needs a final `if: always()`
     aggregator job as the single required check.
2. **Separate per-stack workflow files** using `on: pull_request: paths:` (e.g. `ci-python.yml`,
   `ci-frontend.yml`, `ci-e2e.yml`, `ci-infra.yml`). Each triggers only on its paths; scaffolder
   copies only the relevant ones.
   - Serves **both** goals (run-time path filtering + scaffold-time gating) and sidesteps the
     skipped-required-check trap. Cost: some duplicated checkout/setup boilerplate.

## Current recommendation (to validate when revisited)

**Option 2 — separate per-stack workflow files with `on.paths`.** It serves both the speed and the
scaffold-time goals at once and avoids the required-check trap. Path-targeting lives in the workflow
(`on.paths`); `make` stays "dumb" with granular targets — no git-diff logic in the Makefile, and
local `make lint`/`check`/`test` still runs everything.

Sequencing note: this overlaps **sub-project 4 (stack-aware gating)**, which already governs "copy
only the workflows relevant to the detected stack." Consider merging this restructure into that
sub-project rather than running a standalone cycle.

## Already settled (do NOT redo here)

- Bicep lint lives in its own `ci-infra.yml` (triggered on `infra/**`) + a `make lint-infra` target
  wired into `make lint`/`check`. Decided and specced in the Azure sub-project — it is already an
  instance of Option 2 and should be the template the rest follow.
