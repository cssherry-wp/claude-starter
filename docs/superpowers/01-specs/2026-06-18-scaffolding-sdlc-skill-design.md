# Design: `scaffolding-sdlc` skill

**Date:** 2026-06-18
**Status:** Draft (awaiting user review)
**Author:** brainstormed with Claude Code

## Purpose

Create a reusable Claude Code skill that bootstraps standardized SDLC automation
into a repository. It fuses the proven workflows from two demo repos into one
coherent startup flow:

- `translation_sdlc_demo` — on its **`comment-triage-workflow` branch** (not
  `main`) it carries the mature GitHub Actions set: a real `ci.yml`
  (lint/typecheck/test), a `code-review.yml` with Claude `/code-review` +
  `/security-review` jobs, `claude.yml` (`@claude` commands), and
  `claude-comment-triage.yml` (autonomous comment triage + auto-fix). TS stack:
  biome, vitest, `tsc`.
- `structured_data_demo` (Python/Django + React/Vite) — ruff (lint/format + `S`
  bandit), mypy, pytest, Playwright e2e, stylelint, a `Makefile` orchestrating
  everything, and a gitleaks pre-commit hook. **No GitHub Actions at all.**

The skill combines translation's GitHub automation with structured_data's local
discipline (Makefile + pre-commit + gitleaks) and Python/React toolchains, and
adds the deterministic security gate and PR-status labeling neither repo has.
Result: local task runner + pre-commit hook + Claude commit-doc hook + a full
GitHub Actions suite that runs lint, typecheck, unit, Playwright e2e, and
security on every new PR / PR push.

## Source-of-truth notes (transparency)

- The mature translation workflows live on the **`comment-triage-workflow`
  branch**; `main` only has stale Claude-review stubs. The branch versions are
  canonical.
- **Semgrep** and the **`check-in-progress` / `check-pass` / `check-fail`
  labels** are **not present in either source repo**; scaffolded fresh from
  standard patterns.
- **CodeQL is intentionally excluded** from the gate list. SAST is covered by
  Semgrep (deterministic) plus Claude `/security-review` (semantic).
- **`post_commit_doc.sh` was broken** in the user's global
  `~/.claude/settings.json`: wired as a `Stop` hook but guarded on the
  `PostToolUse`-only field `.tool_input.command`, so it exited before doing
  anything. The global hook was fixed (guard removed; re-amend guard added) and
  verified; the corrected version ships with this skill.

## Two distinct hook mechanisms

- **git hook** (`pre-commit`): lives in `.git/hooks/`, installed via symlink
  (`make install-hooks`), fired by **git** on `git commit`. Runs for every
  committer (Claude or human).
- **Claude Code Stop hook** (`post_commit_doc.sh`): wired in the repo's
  `.claude/settings.json`, fired by the **Claude Code harness** when the agent
  finishes (so it can read `session_id` and amend the commit). Git never invokes
  it; only fires when Claude commits.

Templates are organized by mechanism (`git-hooks/`, `claude-hooks/`).

## Placement & naming

A new dedicated plugin in the `claude-starter` marketplace:

```
plugins/sdlc/
  .claude-plugin/plugin.json
  skills/scaffolding-sdlc/
    SKILL.md
    templates/
      typescript/        # from translation_sdlc_demo
        Makefile  biome.json  vitest.config.ts  tsconfig.base.json
        package-scripts.json  gitignore
      python/            # from structured_data_demo
        Makefile  pyproject-tooling.toml  gitignore
      fullstack/         # Python backend + React/Vite frontend
        Makefile  stylelint.config.js  playwright.config.ts  gitignore
        frontend/        # React/Vite scaffold (see React scaffolding section)
      github/
        workflows/
          ci.yml                    # lint + typecheck + unit + playwright gates
          code-review.yml           # Claude /code-review + /security-review jobs
          security.yml              # gitleaks + dependency audit + semgrep
          claude.yml                # @claude directed commands
          claude-comment-triage.yml # autonomous comment triage + auto-fix
          pr-status-labels.yml      # sets check-in-progress/pass/fail
        dependabot.yml
      git-hooks/
        pre-commit              # gitleaks + make check + typecheck
        README.md
      claude-hooks/
        post_commit_doc.sh      # fixed commit-doc Stop hook
        settings-hooks.json     # snippet wiring it into .claude/settings.json
        README.md
    scripts/
      detect-stack.sh    # inspect repo, print detected stack
      ensure-labels.sh   # idempotent gh label create
    references/
      security-tooling.md
```

## GitHub Actions suite

The four Claude workflows divide cleanly by who initiates and what they consume;
`ci.yml` and `security.yml` are the deterministic gates.

### Deterministic gates (run on new PR / PR push)

Trigger `pull_request: [opened, synchronize, reopened, ready_for_review]`
(+ `push` to default branch where useful).

- **ci.yml** — jobs `lint`, `typecheck`, `unit`, `e2e` (Playwright). Polyglot:
  detect step keys off `package-lock.json` (Node) and `pyproject.toml`/`uv.lock`
  (Python); each job runs only when its stack is present and otherwise no-ops and
  passes (the graceful pattern from translation's `ci.yml`). Jobs call the
  Makefile/npm targets so **local == CI**. The `e2e` job is conditional on a
  frontend.
- **security.yml** — gitleaks (full scan), dependency audit
  (`npm audit` / `pip-audit`), Semgrep. PR triggers + weekly schedule.
- **dependabot.yml** — npm + pip ecosystems, weekly.

### Claude automation workflows

All use `claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}`.

- **code-review.yml** — two jobs, both skipping `[autofix]` commits: `/code-review`
  (via `code-review@claude-code-plugins`) and `/security-review` posting findings
  with `gh pr comment`. Complements the deterministic `security.yml`.
- **claude.yml** — fires on `@claude` mentions; directed, human-initiated
  commands.
- **claude-comment-triage.yml** — fires on non-`@claude` PR/review comments from
  trusted authors (OWNER/MEMBER/COLLABORATOR). Auto-fix path: make the scoped
  change, run `npm test` + `npx biome check .`; if green, commit with `[autofix]`
  subject, push, reply, resolve thread. Respond path (ambiguous / needs judgment
  / checks failed): reply + add `question` label, leave thread open. Loop
  prevention: every posted comment ends with `<!-- claude-autofix -->`; never
  acts on its own marked comments; never submits a PR review. Opt-out via
  `no-automation` label. Depends on the **`github-pr-review@claude-starter`**
  plugin; the marketplace is hardcoded to
  `https://github.com/cssherry-wp/claude-starter.git`.

### PR-status labeling

- **pr-status-labels.yml** — sets `check-in-progress` when checks start and
  `check-pass` / `check-fail` on conclusion (net-new automation).

### Labels ensured at startup (`ensure-labels.sh`, idempotent)

`check-in-progress`, `check-pass`, `check-fail`, `question`, `no-automation`,
`dependencies`, `security`.

## Interactive workflow (SKILL.md playbook)

1. **Detect & report** — inspect manifests, existing `.github/`, `Makefile`,
   hooks, current labels via `gh`. Report what exists vs. missing.
2. **Choose stack & scanners** — present detected stack + menu (TypeScript /
   Python / Fullstack Python+React) with pros/cons. **Pause for the user to
   customize** — not a rigid pick-one. For the React path, **ask at runtime**
   minimal harness vs. full structured_data stack. Confirm which security
   scanners to enable (gitleaks default-on; dependency audit, Dependabot, Semgrep
   opt-in, user verifies).
3. **Local dev loop** — copy/adapt Makefile (or npm scripts) + tool configs
   (biome / ruff / mypy / vitest / pytest / playwright / stylelint), `.gitignore`,
   README, manifest — **only if missing**. Never clobber: detect → diff → ask →
   merge.
4. **git pre-commit hook** — install `git-hooks/pre-commit`, wire
   `make install-hooks`.
5. **Claude commit-doc hook** — install fixed `post_commit_doc.sh`, merge
   `settings-hooks.json` into `.claude/settings.json` as a `Stop` hook; docs land
   in `docs/`.
6. **GitHub Actions** — scaffold the suite above.
7. **Ensure labels** — run `ensure-labels.sh`.
8. **Verify & summarize** — run `make check` / `make test`; list manual
   follow-ups (secrets, branch protection); confirm workflows parse.

## React frontend scaffolding (fullstack path)

The skill **asks at runtime** which depth:

- **Minimal harness (default):** Vite + React 18 + TypeScript, vitest + RTL
  setup, Playwright config, biome + stylelint (scss). No UI component library.
- **Full structured_data stack:** the above plus Radix UI, Tailwind +
  tailwind-merge + tailwindcss-animate, lucide-react, react-router-dom, and a
  couple of example components.

## Safety / idempotency principles

- Never overwrite existing files silently — detect → diff → ask → merge.
- All `gh` operations idempotent (check-then-create).
- Works on fresh and existing repos.
- `ci.yml` jobs no-op gracefully when a stack is absent; `e2e` skipped without a
  frontend.
- `[autofix]` coordination preserved: `code-review.yml` skips `[autofix]`
  commits; triage commits are `[autofix]`-prefixed and marker-signed.
- Doc directory standardized on `docs/`; the commit-doc hook skips re-amending
  commits that already contain a generated doc.

## Testing approach (writing-skills TDD)

Primarily a technique skill, tested via **application scenarios**, baseline-first
(the Iron Law: failing test before the skill):

- **RED** — dispatch a subagent *without* the skill against (a) a fresh TS repo,
  (b) the fullstack `structured_data` repo, (c) a repo with partial setup;
  document inconsistent / incomplete output.
- **GREEN** — re-run *with* the skill; verify a correct, complete scaffold, valid
  parametrized workflows, and that existing files are not clobbered.

This testing is carried out as part of the implementation plan.

## Caveats & manual prerequisites

- Requires authenticated `gh` CLI with repo admin (labels, branch protection).
- Claude workflows need the `CLAUDE_CODE_OAUTH_TOKEN` repo secret; Semgrep
  optionally `SEMGREP_APP_TOKEN`.
- `claude-comment-triage.yml` hardcodes the `cssherry-wp/claude-starter`
  marketplace; other orgs must hand-edit.
- Semgrep, `pr-status-labels.yml`, and the `check-*` labels are net-new.
- CodeQL is intentionally excluded from the gate list.
- The commit-doc hook records the pre-amend short hash in the generated doc (a
  pre-existing cosmetic quirk, not addressed here).
