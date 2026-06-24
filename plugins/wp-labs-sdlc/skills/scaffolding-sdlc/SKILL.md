---
name: scaffolding-sdlc
description: Use when starting a new repo or adding SDLC automation to an existing one — sets up lint, unit tests, Playwright e2e, security scanning, Dependabot, PR-status labels, pre-commit hooks, and Claude PR automation that run on every PR. Use when a repo lacks CI gates, has no pre-commit checks, or needs standardized GitHub Actions.
---

# Scaffolding SDLC

## Overview

Interactively bootstrap standardized SDLC automation into a repo: a runnable
starter app (for a greenfield repo), a local task runner (Makefile), a git
pre-commit hook, GitHub Actions PR gates (lint,
typecheck, unit, Playwright e2e, security), Dependabot, PR-status labels, four
Claude PR-automation workflows, and an optional hosting layer (Docker +
docker-compose + Azure Bicep deploy) for web-app stacks.

**Core principle:** local == CI (both call the same Makefile targets), and never
clobber existing files — detect, diff, ask, merge. On an existing repo, audit
the full inventory and add only the missing pieces.

## When to use

- Starting a fresh repo that needs CI/quality gates.
- An existing repo with no `.github/workflows/`, no pre-commit checks, or
  inconsistent tooling.

## Prerequisites (tell the user up front)

- Authenticated `gh` CLI with repo admin (labels, branch protection).
- Repo secrets to add manually: `CLAUDE_CODE_OAUTH_TOKEN` (required for the four
  Claude workflows), `SEMGREP_APP_TOKEN` (optional).
- For `pr-rebase.yml` to re-trigger CI on rebased commits, add **either** a
  GitHub App (preferred) — secrets `REBASE_APP_ID` + `REBASE_APP_PRIVATE_KEY`,
  App permissions Contents: write and Pull requests: write, installed on the
  repo — **or** a fine-grained PAT `REBASE_TOKEN` (same two permissions) as a
  fallback. Without either it falls back to `GITHUB_TOKEN`, which still rebases
  but does not re-run CI.
- `gitleaks` installed locally for the pre-commit secret scan
  (`brew install gitleaks`).

## Workflow

Run these steps in order. The template root is this skill's `templates/`
directory; copy from there.

1. **Detect & audit.** Run `scripts/detect-stack.sh` in the target repo and note
   its conventions: package manager (pip vs uv), config-file style (standalone
   `ruff.toml`/`pytest.ini` vs `[tool.*]`), project subdirectory (manifests under
   `app/`, `app/frontend/`, etc.), and existing frontend linter.

   Then produce a **scaffold inventory** — go through EVERY component this skill
   can add and mark each present / partial / missing:
   - dev-loop: `Makefile`, tool configs, `.gitignore`, manifest
   - starter app (greenfield only)
   - `git-hooks/pre-commit`
   - each workflow: `ci.yml`, `security.yml`, `code-review.yml` (two jobs — a
     read-only `review` job runs `change-review` and a privileged `apply` job
     applies its patch + posts findings), `claude.yml`,
     `claude-comment-triage.yml`, `pr-status-labels.yml`, `pr-rebase.yml`
   - `dependabot.yml`; the managed labels; hosting (`Dockerfile`,
     `docker-compose.yml`, `infra/` Bicep, `azure-deploy.yml`)

   Present the inventory to the user. **On an existing repo, add only the
   missing pieces** and **explicitly ask about each gap** before adding it —
   don't assume. **Never overwrite existing files silently:** for anything that
   already exists, show the diff and ask. **Adapt, don't impose:** where the repo
   already has a convention, conform to it (e.g. add `pip-audit` for a pip repo,
   wire CI `working-directory` to the project subdir, call the repo's existing
   `make` targets) instead of forcing the template's defaults.

2. **Choose stack & scanners.** Present the detected stack and the menu —
   **TypeScript**, **Python**, or **Fullstack (Python + React)** — with brief
   pros/cons. **Pause and let the user customize** the choice; do not force a
   single option. For the Fullstack/React path, ask whether to scaffold the
   **minimal React harness** (default) or the **full structured_data stack**
   (Radix + Tailwind + lucide + react-router) — see
   `templates/fullstack/frontend/README.md`. Confirm which security scanners to
   enable (gitleaks default-on; dependency audit, Dependabot, Semgrep opt-in) —
   see `references/security-tooling.md`.

3. **Local dev loop.** Copy the chosen stack's templates
   (`templates/<stack>/`): the `Makefile`, tool configs, and `gitignore` →
   `.gitignore`. Merge `package-scripts.json` / `pyproject-tooling.toml` into an
   existing manifest (do not overwrite the whole file). Create README and the
   manifest only if missing.

   **Starter app (greenfield only).** If the repo has no source yet, also copy
   the stack's runnable skeleton from `templates/<stack>/scaffold/` (TS: a typed
   CLI library; Python: a Django + DRF API; Fullstack: that API plus a React +
   Router frontend) so `make test`/`make lint` pass out of the box. For the
   Fullstack/React choice from step 2: the **minimal harness** is
   `templates/fullstack/frontend/` (configs only); the **full app** is
   `templates/fullstack/scaffold/`. **Never copy the scaffold over existing
   source** — skip any file that already exists.

4. **git pre-commit hook.** Copy `templates/git-hooks/pre-commit` →
   `.sdlc-hooks/pre-commit`, then run `make install-hooks` to symlink it.

5. **GitHub Actions.** Copy `templates/github/workflows/*.yml` →
   `.github/workflows/` (gates `ci.yml`/`security.yml`, the Claude automation
   trio, `pr-status-labels.yml`, and `pr-rebase.yml`) and
   `templates/github/dependabot.yml` → `.github/dependabot.yml`. Skip any
   workflow the user opted out of (e.g. no Semgrep → leave the `semgrep` job out
   of `security.yml`). `pr-rebase.yml` auto-rebases behind PRs onto `main` and
   force-pushes with lease; remind the user to add the GitHub App (preferred) or
   `REBASE_TOKEN` PAT secrets so rebased pushes re-trigger CI (see Prerequisites).

6. **Hosting (web-app stacks).** For Python/Fullstack, offer the hosting layer:
   copy `templates/<stack>/hosting/` (`Dockerfile`, `.dockerignore`,
   `docker-compose.yml`) to the repo root, `templates/azure/infra/` → `infra/`,
   `templates/azure/workflows/azure-deploy.yml` → `.github/workflows/`, and
   `templates/azure/HOSTING.md`. Local: `docker compose up --build`. Deploy needs
   the Azure OIDC secrets + repo variables in `HOSTING.md` (the deploy job
   no-ops until `AZURE_WEBAPP_NAME` is set). The TS CLI-library stack has no
   hosting layer. Skip if the user declines.

7. **Ensure labels.** Run `scripts/ensure-labels.sh` (idempotent). Creates
   `check-in-progress`, `check-pass`, `check-fail`, `question`, `no-automation`,
   `dependencies`, `security`, `needs-rebase`.

8. **Verify & summarize.** Run `make check` and `make test` locally and report
   results. Summarize what was created/changed and list manual follow-ups: add
   the repo secrets above (incl. Azure OIDC if hosting was added), and
   (recommended) enable branch protection requiring the CI checks.

## Key facts

- `claude-comment-triage.yml` loads the `wp-labs-standards@wp-labs-starter`
  plugin (which provides the `github-pr-review` skill) and hardcodes the
  marketplace `cssherry-wp/wp-labs-starter`.
- `[autofix]` coordination: triage commits are `[autofix]`-prefixed and signed
  `<!-- claude-autofix -->`; `code-review.yml` skips them.
- **Branch protection required:** `code-review.yml`'s `apply` job pushes an
  `[autofix]` commit to the PR branch from an agent-derived patch, and the agent
  runs only on same-repo PRs (forks get no secrets). Consuming repos MUST
  branch-protect `main`/release branches with required human review and MUST NOT
  auto-merge on `[autofix]`/bot authorship — that human-review gate is what bounds a
  prompt-injected patch.

## Common mistakes

- Overwriting an existing `package.json`/`pyproject.toml`/`.claude/settings.json`
  instead of merging — always merge.
- Forgetting the `CLAUDE_CODE_OAUTH_TOKEN` secret — the four Claude workflows
  silently no-op or fail without it.
- Scaffolding the Playwright `e2e` job for a backend-only repo — it is for
  frontends; the CI job already no-ops, but don't promise e2e where there's no UI.
