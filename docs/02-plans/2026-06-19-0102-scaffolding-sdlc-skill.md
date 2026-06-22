# Scaffolding-SDLC Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new `scaffolding-sdlc` skill (in a new `sdlc` plugin) that interactively bootstraps standardized SDLC automation — local task runner, git pre-commit hook, Claude commit-doc hook, GitHub Actions PR gates, security scanning, Dependabot, and PR-status labels — into any repo.

**Architecture:** A single interactive `SKILL.md` playbook backed by per-stack template directories and helper scripts. The skill detects the repo's stack, presents options, then copies/adapts templates (never clobbering existing files). The heavy/reusable content (workflow YAML, Makefiles, configs, scripts) lives in `templates/` and `scripts/`; `SKILL.md` orchestrates.

**Tech Stack:** Bash (scripts + hooks), GitHub Actions YAML, GNU Make, biome/vitest/tsc (TS), ruff/mypy/pytest (Python), Playwright (e2e), gitleaks/Semgrep/Dependabot (security), `gh` CLI.

**Spec:** `docs/01-specs/2026-06-18-1911-scaffolding-sdlc-skill-design.md`

## Global Constraints

- Plugin lives at `plugins/sdlc/`; skill at `plugins/sdlc/skills/scaffolding-sdlc/`.
- Doc directory convention is `docs/` (plural); doc/spec/plan files are named `YYYY-MM-DD-HHmm-<topic>.md`.
- CodeQL is excluded from the gate list; SAST = Semgrep (deterministic) + Claude `/security-review` (semantic).
- `claude-comment-triage.yml` hardcodes the marketplace `https://github.com/cssherry-wp/claude-starter.git` with plugin `github-pr-review@claude-starter`.
- Labels managed: `check-in-progress`, `check-pass`, `check-fail`, `question`, `no-automation`, `dependencies`, `security`, `needs-rebase`.
- **Adapt, don't impose.** On an existing repo the skill detects and conforms to the repo's actual conventions — package manager (pip vs uv), config-file style (standalone `ruff.toml`/`pytest.ini` vs `[tool.*]` in `pyproject.toml`), **project subdirectory** (manifests under `app/`, `app/frontend/`, etc. rather than the repo root), existing frontend linter (ESLint/Prettier vs biome), and existing Makefile target names. It imposes its own templates only on a greenfield repo with no such conventions.
- Claude workflows use `claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}`.
- Autofix coordination: triage commits are prefixed `[autofix]` and signed `<!-- claude-autofix -->`; `code-review.yml` skips `[autofix]` commits.
- Idempotency: never overwrite existing files silently (detect → diff → ask → merge); all `gh` label ops are check-then-create.
- Commit message format follows the team convention (subject ≤50 chars; `Logic:` / `Alternatives considered:` / `Caveats/assumptions:` body). Each task's final commit uses this format.
- Source repos for verbatim/adapted templates:
  - TS: `/Users/sherryzhou/code/translation_sdlc_demo` (`main` for configs; `comment-triage-workflow` branch for `.github/workflows/`).
  - Python/React: `/Users/sherryzhou/code/structured_data_demo` (`app/` subtree).
- Validation tooling available locally: `actionlint`, `shellcheck`, `jq`, `python3`, `gh`, `node`, `uv`. NOT available: `gitleaks`, `yq` (use `python3 -c 'import yaml...'` for YAML validation; gitleaks is a runtime dependency only).

---

### Task 1: Plugin skeleton + marketplace registration

**Files:**
- Create: `plugins/sdlc/.claude-plugin/plugin.json`
- Create: `plugins/sdlc/skills/scaffolding-sdlc/SKILL.md` (stub — full content in Task 12)
- Modify: `.claude-plugin/marketplace.json` (append `sdlc` plugin entry)

**Interfaces:**
- Produces: a registered `sdlc` plugin discoverable by the marketplace; skill directory path `plugins/sdlc/skills/scaffolding-sdlc/`.

- [ ] **Step 1: Write the failing test**

```bash
test -f plugins/sdlc/.claude-plugin/plugin.json \
  && jq -e '.name == "sdlc"' plugins/sdlc/.claude-plugin/plugin.json \
  && jq -e '.plugins[] | select(.name=="sdlc")' .claude-plugin/marketplace.json
```

- [ ] **Step 2: Run it to verify it fails**

Run the Step 1 command. Expected: FAIL (files absent / no `sdlc` entry).

- [ ] **Step 3: Create `plugins/sdlc/.claude-plugin/plugin.json`**

```json
{
  "name": "sdlc",
  "version": "0.1.0",
  "description": "Repo SDLC bootstrapping: scaffolding-sdlc skill wires lint, tests, Playwright e2e, security scanning, Dependabot, PR-status labels, and Claude PR automation onto new or existing repos.",
  "author": {
    "name": "Sherry Zhou",
    "email": "szhou@wp-labs.ai"
  }
}
```

- [ ] **Step 4: Create the SKILL.md stub**

```markdown
---
name: scaffolding-sdlc
description: Use when starting a new repo or adding SDLC automation to an existing one — sets up lint, unit tests, Playwright e2e, security scanning, Dependabot, PR-status labels, pre-commit hooks, and Claude PR automation that run on every PR. Use when a repo lacks CI gates, has no pre-commit checks, or needs standardized GitHub Actions.
---

# Scaffolding SDLC

> Stub — full playbook authored in Task 12.
```

- [ ] **Step 5: Append the `sdlc` entry to `.claude-plugin/marketplace.json`**

Add this object to the `plugins` array (after the `superpowers-team` entry):

```json
{
  "name": "sdlc",
  "source": "./plugins/sdlc",
  "description": "Repo SDLC bootstrapping: the scaffolding-sdlc skill wires lint/test/e2e/security gates, Dependabot, PR-status labels, pre-commit + commit-doc hooks, and Claude PR automation onto a repo.",
  "category": "development",
  "version": "0.1.0"
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run the Step 1 command plus: `python3 -c "import json;json.load(open('.claude-plugin/marketplace.json'))"`
Expected: all succeed (exit 0), marketplace.json is valid JSON.

- [ ] **Step 7: Commit**

```bash
git add plugins/sdlc/.claude-plugin/plugin.json plugins/sdlc/skills/scaffolding-sdlc/SKILL.md .claude-plugin/marketplace.json
git commit -m "$(cat <<'EOF'
Add sdlc plugin skeleton

Logic: Register the new sdlc plugin + scaffolding-sdlc skill stub so the
marketplace exposes it; later tasks fill in templates and the playbook.

Caveats/assumptions:
- SKILL.md is a stub; full interactive playbook lands in Task 12.
EOF
)"
```

---

### Task 2: `detect-stack.sh` helper script

**Files:**
- Create: `plugins/sdlc/skills/scaffolding-sdlc/scripts/detect-stack.sh`

**Interfaces:**
- Produces: `detect-stack.sh [DIR]` — inspects DIR (default `.`) and prints one or more of `typescript`, `python`, `frontend` (one per line). Exit 0 always. Used by SKILL.md Step 1 (detect & report).
- Detection rules: `typescript` if `package.json` or `*.ts`/`tsconfig*.json` present at top level or one level deep; `python` if `pyproject.toml`/`requirements*.txt`/`*.py`; `frontend` if a `package.json` declares `react` or a `vite.config.*`/`frontend/` dir exists.

- [ ] **Step 1: Write the failing test**

```bash
TMP=$(mktemp -d); cd "$TMP"
echo '{"dependencies":{"react":"^18"}}' > package.json
touch tsconfig.json; touch pyproject.toml
OUT=$(bash "$OLDPWD/plugins/sdlc/skills/scaffolding-sdlc/scripts/detect-stack.sh" .)
echo "$OUT" | grep -qx typescript && echo "$OUT" | grep -qx python && echo "$OUT" | grep -qx frontend && echo PASS || echo FAIL
cd "$OLDPWD"; rm -rf "$TMP"
```

- [ ] **Step 2: Run it to verify it fails**

Run Step 1. Expected: FAIL (script does not exist → `bash: ... No such file`).

- [ ] **Step 3: Write the script**

```bash
#!/usr/bin/env bash
# Detect the SDLC stack(s) present in a directory.
# Prints any of: typescript, python, frontend (one per line). Always exits 0.
set -euo pipefail
DIR="${1:-.}"
cd "$DIR" 2>/dev/null || exit 0

emit() { printf '%s\n' "$1"; }

# TypeScript / Node
if [ -f package.json ] || ls -1 tsconfig*.json >/dev/null 2>&1 \
   || find . -maxdepth 2 -name '*.ts' -not -path '*/node_modules/*' | head -1 | grep -q .; then
  emit typescript
fi

# Python
if [ -f pyproject.toml ] || ls -1 requirements*.txt >/dev/null 2>&1 \
   || find . -maxdepth 2 -name '*.py' -not -path '*/.venv/*' | head -1 | grep -q .; then
  emit python
fi

# Frontend (React/Vite)
if find . -maxdepth 2 -name 'vite.config.*' | head -1 | grep -q . \
   || [ -d frontend ] \
   || { [ -f package.json ] && grep -q '"react"' package.json 2>/dev/null; }; then
  emit frontend
fi
exit 0
```

- [ ] **Step 4: Make executable and run tests to verify they pass**

Run: `chmod +x plugins/sdlc/skills/scaffolding-sdlc/scripts/detect-stack.sh` then the Step 1 command.
Also test single-stack: a dir with only `pyproject.toml` prints exactly `python`.
Expected: PASS for both. Then `shellcheck plugins/sdlc/skills/scaffolding-sdlc/scripts/detect-stack.sh` → no errors.

- [ ] **Step 5: Commit**

```bash
git add plugins/sdlc/skills/scaffolding-sdlc/scripts/detect-stack.sh
git commit -m "$(cat <<'EOF'
Add detect-stack.sh

Logic: The skill needs a deterministic, testable stack detector so the
playbook can report what exists before scaffolding.

Caveats/assumptions:
- maxdepth 2 covers monorepo lib/apps layouts without deep scans.
EOF
)"
```

---

### Task 3: `ensure-labels.sh` helper script

**Files:**
- Create: `plugins/sdlc/skills/scaffolding-sdlc/scripts/ensure-labels.sh`

**Interfaces:**
- Produces: `ensure-labels.sh` — idempotently creates the managed label set in the current repo via `gh label create ... --force`. Reads no args. Requires authenticated `gh`. Prints each label action.
- Managed labels (name, color, description) per Global Constraints.

- [ ] **Step 1: Write the failing test**

```bash
grep -c 'gh label create' plugins/sdlc/skills/scaffolding-sdlc/scripts/ensure-labels.sh
# Expected after impl: 8
```

- [ ] **Step 2: Run it to verify it fails**

Run Step 1. Expected: FAIL (`No such file`).

- [ ] **Step 3: Write the script**

```bash
#!/usr/bin/env bash
# Idempotently ensure the team's managed PR-automation labels exist.
# Requires an authenticated `gh` CLI in a repo with label write access.
set -euo pipefail

ensure() {
  local name="$1" color="$2" desc="$3"
  # --force updates color/description if the label already exists, and creates it otherwise.
  gh label create "$name" --color "$color" --description "$desc" --force
  echo "ensured: $name"
}

ensure "check-in-progress" "fbca04" "Automated checks are running"
ensure "check-pass"        "0e8a16" "Automated checks passed"
ensure "check-fail"        "d73a4a" "Automated checks failed"
ensure "question"          "d876e3" "Needs a human decision (set by comment triage)"
ensure "no-automation"     "ededed" "Opt out of Claude comment-triage auto-fix on this PR"
ensure "dependencies"      "0366d6" "Dependency updates (Dependabot)"
ensure "security"          "b60205" "Security finding or security-related change"
ensure "needs-rebase"      "e99695" "PR is behind main and auto-rebase hit conflicts"
```

- [ ] **Step 4: Run tests to verify they pass**

Run Step 1 (expect `8`). Run `shellcheck plugins/sdlc/skills/scaffolding-sdlc/scripts/ensure-labels.sh` (no errors). Run `bash -n` on it. (No live `gh` call in tests — that requires a real repo; the SKILL.md runs it at scaffold time.)

- [ ] **Step 5: Commit**

```bash
git add plugins/sdlc/skills/scaffolding-sdlc/scripts/ensure-labels.sh
git commit -m "$(cat <<'EOF'
Add ensure-labels.sh

Logic: PR-status and triage workflows depend on a fixed label set;
--force makes creation idempotent and safe to re-run.

Caveats/assumptions:
- Requires authenticated gh with label write scope (documented in SKILL.md).
EOF
)"
```

---

### Task 4: TypeScript dev-loop templates

**Files:**
- Create: `plugins/sdlc/skills/scaffolding-sdlc/templates/typescript/biome.json`
- Create: `.../templates/typescript/vitest.config.ts`
- Create: `.../templates/typescript/tsconfig.base.json`
- Create: `.../templates/typescript/package-scripts.json`
- Create: `.../templates/typescript/Makefile`
- Create: `.../templates/typescript/gitignore`

**Interfaces:**
- Produces: TS toolchain templates the playbook copies for a `typescript` stack. `package-scripts.json` holds the `scripts` block to merge into a target `package.json`.

- [ ] **Step 1: Write the failing test**

```bash
T=plugins/sdlc/skills/scaffolding-sdlc/templates/typescript
for f in biome.json vitest.config.ts tsconfig.base.json package-scripts.json Makefile gitignore; do test -f "$T/$f" || { echo "MISSING $f"; }; done
jq -e . "$T/biome.json" && jq -e '.scripts.lint and .scripts.test and .scripts.typecheck' "$T/package-scripts.json"
```

- [ ] **Step 2: Run it to verify it fails**

Run Step 1. Expected: FAIL (files MISSING).

- [ ] **Step 3: Create `biome.json`** (copy verbatim from `/Users/sherryzhou/code/translation_sdlc_demo/biome.json`):

```json
{
  "$schema": "https://biomejs.dev/schemas/1.9.4/schema.json",
  "organizeImports": { "enabled": true },
  "linter": {
    "enabled": true,
    "rules": { "recommended": true, "suspicious": { "noExplicitAny": "error" } }
  },
  "formatter": { "enabled": true, "indentStyle": "space", "indentWidth": 2 },
  "files": {
    "ignore": ["dist", "**/dist/**", ".astro", "**/.astro/**", "**/env.d.ts"]
  }
}
```

- [ ] **Step 4: Create `vitest.config.ts`**:

```typescript
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["**/test/**/*.test.ts", "**/src/**/*.test.ts"],
    exclude: ["**/node_modules/**", "**/dist/**", "**/.astro/**"],
  },
});
```

- [ ] **Step 5: Create `tsconfig.base.json`** (copy from `/Users/sherryzhou/code/translation_sdlc_demo/tsconfig.base.json`; if absent there, use this):

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "noEmit": true
  }
}
```

- [ ] **Step 6: Create `package-scripts.json`** (the scripts block to merge into a target `package.json`):

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "biome check .",
    "format": "biome format --write .",
    "typecheck": "tsc -b --pretty"
  }
}
```

- [ ] **Step 7: Create `Makefile`** (thin wrapper so local == CI):

```makefile
# TypeScript SDLC targets — scaffolded by scaffolding-sdlc.
.PHONY: install lint format check typecheck test test-e2e install-hooks

install:
	npm ci

lint:
	npx biome check .

format:
	npx biome format --write .

# CI mode: no file modifications.
check: lint typecheck

typecheck:
	npx tsc -b --pretty

test:
	npx vitest run

test-e2e:
	npx playwright test

install-hooks:
	@if [ -d .git ]; then ln -sf ../../.sdlc-hooks/pre-commit .git/hooks/pre-commit && echo "pre-commit installed"; else echo "not a git repo"; fi
```

- [ ] **Step 8: Create `gitignore`** (template; the playbook writes it as `.gitignore` only if missing, else merges):

```gitignore
node_modules/
dist/
.astro/
coverage/
*.log
.env
.env.*
.DS_Store
```

- [ ] **Step 9: Run tests to verify they pass**

Run Step 1. Expected: all files present, `biome.json` and `package-scripts.json` valid JSON with required keys. Run `make -n -f "$T/Makefile" check` to confirm the Makefile parses.

- [ ] **Step 10: Commit**

```bash
git add plugins/sdlc/skills/scaffolding-sdlc/templates/typescript
git commit -m "$(cat <<'EOF'
Add TypeScript dev-loop templates

Logic: Mirror translation_sdlc_demo's biome/vitest/tsc setup as templates
and add a Makefile so CI calls the same targets as local dev.

Caveats/assumptions:
- package-scripts.json is merged into an existing package.json, not copied.
EOF
)"
```

---

### Task 5: Python dev-loop templates

**Files:**
- Create: `.../templates/python/pyproject-tooling.toml`
- Create: `.../templates/python/Makefile`
- Create: `.../templates/python/gitignore`

**Interfaces:**
- Produces: Python toolchain templates. `pyproject-tooling.toml` holds the `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` blocks to merge into a target `pyproject.toml`.

- [ ] **Step 1: Write the failing test**

```bash
T=plugins/sdlc/skills/scaffolding-sdlc/templates/python
test -f "$T/pyproject-tooling.toml" && test -f "$T/Makefile" && test -f "$T/gitignore"
python3 -c "import tomllib;d=tomllib.load(open('$T/pyproject-tooling.toml','rb'));assert d['tool']['ruff'] and d['tool']['mypy'] and d['tool']['pytest']"
```

- [ ] **Step 2: Run it to verify it fails**

Run Step 1. Expected: FAIL (files absent).

- [ ] **Step 3: Create `pyproject-tooling.toml`** (adapted from `/Users/sherryzhou/code/structured_data_demo/app/pyproject.toml`):

```toml
[tool.pytest.ini_options]
python_files = ["tests/test_*.py", "test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 88
target-version = "py313"
extend-exclude = ["**/migrations/*.py"]

[tool.ruff.lint]
select = ["E", "W", "F", "B", "BLE", "UP", "N", "SIM", "RUF", "S", "I"]
fixable = ["ALL"]
unfixable = []

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]
"**/tests/test_*.py" = ["S101"]

[tool.ruff.format]
quote-style = "double"
line-ending = "lf"

[tool.mypy]
python_version = "3.13"
strict = true
ignore_missing_imports = true
follow_imports = "skip"
exclude = ["*/migrations/*", "*/test_*", "*/tests.py"]
```

- [ ] **Step 4: Create `Makefile`**:

```makefile
# Python SDLC targets — scaffolded by scaffolding-sdlc.
.PHONY: install lint format check typecheck test install-hooks

install:
	uv sync --extra dev

lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

# CI mode: no file modifications.
check:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy . || echo "WARNING: mypy found issues — review output above"

test:
	uv run pytest

install-hooks:
	@if [ -d .git ]; then ln -sf ../../.sdlc-hooks/pre-commit .git/hooks/pre-commit && echo "pre-commit installed"; else echo "not a git repo"; fi
```

- [ ] **Step 5: Create `gitignore`**:

```gitignore
__pycache__/
*.pyc
.venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/
*.egg-info/
.env
.env.*
.DS_Store
db.sqlite3
```

- [ ] **Step 6: Run tests to verify they pass**

Run Step 1 (tomllib parse asserts the three tool tables exist). Run `make -n -f "$T/Makefile" check`.
Validate ruff config: `cd $(mktemp -d) && cp "$OLDPWD/$T/pyproject-tooling.toml" pyproject.toml && uv run ruff check --no-cache . ; cd -` (expect ruff to load config without a config error; "no files" is fine).

- [ ] **Step 7: Commit**

```bash
git add plugins/sdlc/skills/scaffolding-sdlc/templates/python
git commit -m "$(cat <<'EOF'
Add Python dev-loop templates

Logic: Mirror structured_data_demo's ruff (incl. S security rules), mypy,
and pytest config as a mergeable tooling block plus a uv-based Makefile.

Alternatives considered:
- pip/venv instead of uv: rejected; source repo standardizes on uv.

Caveats/assumptions:
- Django-specific mypy plugin/stubs omitted; added per-repo when Django present.
EOF
)"
```

---

### Task 6: Fullstack + React frontend templates

**Files:**
- Create: `.../templates/fullstack/Makefile`
- Create: `.../templates/fullstack/stylelint.config.js`
- Create: `.../templates/fullstack/playwright.config.ts`
- Create: `.../templates/fullstack/gitignore`
- Create: `.../templates/fullstack/frontend/package.json` (minimal harness baseline)
- Create: `.../templates/fullstack/frontend/vite.config.ts`
- Create: `.../templates/fullstack/frontend/test.setup.ts`
- Create: `.../templates/fullstack/frontend/README.md` (documents minimal-vs-full choice)

**Interfaces:**
- Produces: fullstack templates combining the Python backend Makefile with a React/Vite frontend. The frontend baseline is the **minimal harness**; SKILL.md (Task 12) documents how to upgrade to the full structured_data stack.

- [ ] **Step 1: Write the failing test**

```bash
T=plugins/sdlc/skills/scaffolding-sdlc/templates/fullstack
for f in Makefile stylelint.config.js playwright.config.ts gitignore frontend/package.json frontend/vite.config.ts frontend/test.setup.ts frontend/README.md; do test -f "$T/$f" || echo "MISSING $f"; done
jq -e '.scripts.test and .scripts["test:e2e"] and .scripts.lint' "$T/frontend/package.json"
```

- [ ] **Step 2: Run it to verify it fails**

Run Step 1. Expected: MISSING lines printed.

- [ ] **Step 3: Create `Makefile`** (combines Python + frontend; adapted from `/Users/sherryzhou/code/structured_data_demo/app/Makefile`):

```makefile
# Fullstack (Python backend + React/Vite frontend) SDLC targets.
.PHONY: install lint lint-python lint-js lint-css format check check-python check-js check-css typecheck test test-python test-js test-e2e install-hooks

install:
	uv sync --extra dev
	npm install

lint: lint-python lint-js lint-css
lint-python: ; uv run ruff check .
lint-js: ; npx biome check frontend/src/
lint-css: ; npx stylelint "frontend/src/**/*.scss"

format:
	uv run ruff format .
	uv run ruff check --fix .
	npx biome format --write frontend/src/
	npx stylelint --fix "frontend/src/**/*.scss"

# CI mode: no file modifications.
check: check-python check-js check-css
check-python:
	uv run ruff check .
	uv run ruff format --check .
check-js:
	npx tsc --noEmit
	npx biome check frontend/src/
check-css: ; npx stylelint "frontend/src/**/*.scss"

typecheck: check-js
	uv run mypy . || echo "WARNING: mypy found issues — review output above"

test: test-python test-js
test-python: ; uv run pytest
test-js: ; npm test
test-e2e: ; npm run test:e2e

install-hooks:
	@if [ -d .git ]; then ln -sf ../../.sdlc-hooks/pre-commit .git/hooks/pre-commit && echo "pre-commit installed"; else echo "not a git repo"; fi
```

- [ ] **Step 4: Create `stylelint.config.js`**:

```javascript
/** @type {import('stylelint').Config} */
export default {
  extends: ["stylelint-config-standard-scss"],
};
```

- [ ] **Step 5: Create `playwright.config.ts`**:

```typescript
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./frontend/e2e",
  use: { baseURL: "http://localhost:5173" },
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
  },
});
```

- [ ] **Step 6: Create `frontend/package.json`** (minimal React 18 + Vite + vitest/RTL + Playwright harness):

```json
{
  "name": "frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "lint": "biome check frontend/src/",
    "format": "biome format --write frontend/src/",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@biomejs/biome": "^2.0.0",
    "@playwright/test": "^1.49.0",
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/react": "^16.1.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.0.0",
    "jsdom": "^25.0.0",
    "sass": "^1.101.0",
    "stylelint": "^16.0.0",
    "stylelint-config-standard-scss": "^13.1.0",
    "typescript": "^5.8.0",
    "vite": "^5.0.0",
    "vitest": "^2.1.0"
  }
}
```

- [ ] **Step 7: Create `frontend/vite.config.ts`**:

```typescript
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./test.setup.ts"],
  },
});
```

- [ ] **Step 8: Create `frontend/test.setup.ts`**:

```typescript
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 9: Create `frontend/README.md`**:

```markdown
# Frontend scaffold

This is the **minimal harness**: Vite + React 18 + TypeScript + vitest/RTL +
Playwright + biome + stylelint. No UI component library is included.

To upgrade to the **full structured_data stack**, add: `@radix-ui/*`,
`tailwindcss` + `tailwind-merge` + `tailwindcss-animate`, `lucide-react`,
`react-router-dom`, `class-variance-authority`, `clsx`, plus Tailwind/PostCSS
config. The scaffolding-sdlc skill prompts for this choice at scaffold time.
```

- [ ] **Step 10: Run tests to verify they pass**

Run Step 1. Expected: no MISSING lines; frontend `package.json` has the required scripts. Run `make -n -f "$T/Makefile" check` and `node --check "$T/stylelint.config.js"`.

- [ ] **Step 11: Commit**

```bash
git add plugins/sdlc/skills/scaffolding-sdlc/templates/fullstack
git commit -m "$(cat <<'EOF'
Add fullstack + React frontend templates

Logic: Combine the Python backend Makefile with a minimal React/Vite +
vitest/RTL + Playwright harness derived from structured_data_demo; document
the optional upgrade to the full Radix/Tailwind stack.

Alternatives considered:
- Ship the full Radix/Tailwind stack by default: rejected; skill asks at
  runtime to avoid imposing UI deps.
EOF
)"
```

---

### Task 7: git pre-commit hook template

**Files:**
- Create: `.../templates/git-hooks/pre-commit`
- Create: `.../templates/git-hooks/README.md`

**Interfaces:**
- Produces: a git `pre-commit` hook (gitleaks secret scan + `make check` + typecheck). Installed by `make install-hooks` symlinking from `.sdlc-hooks/pre-commit`.

- [ ] **Step 1: Write the failing test**

```bash
T=plugins/sdlc/skills/scaffolding-sdlc/templates/git-hooks
test -f "$T/pre-commit" && test -f "$T/README.md" && bash -n "$T/pre-commit" && echo PASS
```

- [ ] **Step 2: Run it to verify it fails**

Run Step 1. Expected: FAIL (absent).

- [ ] **Step 3: Create `pre-commit`** (adapted from `/Users/sherryzhou/code/structured_data_demo/hooks/pre-commit`):

```bash
#!/bin/sh
# Pre-commit: secret scan + lint/format/type checks before allowing a commit.
# Installed via `make install-hooks`.
set -e

if command -v gitleaks >/dev/null 2>&1; then
  echo "Scanning for secrets..."
  gitleaks protect --staged --verbose
else
  echo "WARNING: gitleaks not installed; skipping secret scan (brew install gitleaks)"
fi

echo "Running checks..."
make check
make typecheck || true

echo "Pre-commit checks complete."
```

- [ ] **Step 4: Create `README.md`**:

```markdown
# git-hooks/pre-commit

A **git hook** (not a Claude hook). Git runs it on every `git commit`.

**Install:** `make install-hooks` symlinks `.git/hooks/pre-commit` →
`.sdlc-hooks/pre-commit` (the skill copies this file there at scaffold time).

**Runs:** gitleaks secret scan (if installed) → `make check` → `make typecheck`.
A non-zero exit from gitleaks or `make check` aborts the commit.
```

- [ ] **Step 5: Run tests to verify they pass**

Run Step 1 (expect PASS). Run `shellcheck -s sh "$T/pre-commit"` (no errors).

- [ ] **Step 6: Commit**

```bash
git add plugins/sdlc/skills/scaffolding-sdlc/templates/git-hooks
git commit -m "$(cat <<'EOF'
Add git pre-commit hook template

Logic: Port structured_data_demo's gitleaks+checks pre-commit; degrade
gracefully when gitleaks is absent rather than blocking all commits.

Caveats/assumptions:
- gitleaks is a runtime dependency; README documents brew install.
EOF
)"
```

---

### Task 8: Claude commit-doc hook template

**Files:**
- Create: `.../templates/claude-hooks/post_commit_doc.sh`
- Create: `.../templates/claude-hooks/settings-hooks.json`
- Create: `.../templates/claude-hooks/README.md`

**Interfaces:**
- Produces: the **fixed** commit-doc Stop hook (from `/Users/sherryzhou/.claude/hooks/post_commit_doc.sh`), a `.claude/settings.json` snippet wiring it as a `Stop` hook, and a README explaining the mechanism.

- [ ] **Step 1: Write the failing test**

```bash
T=plugins/sdlc/skills/scaffolding-sdlc/templates/claude-hooks
test -f "$T/post_commit_doc.sh" && bash -n "$T/post_commit_doc.sh"
# The fixed hook must NOT reference tool_input.command (that was the bug).
! grep -q 'tool_input.command' "$T/post_commit_doc.sh" && echo "PASS: no tool_input.command"
jq -e '.Stop' "$T/settings-hooks.json"
```

- [ ] **Step 2: Run it to verify it fails**

Run Step 1. Expected: FAIL (files absent).

- [ ] **Step 3: Create `post_commit_doc.sh`** (copy the fixed global hook verbatim):

```bash
cp /Users/sherryzhou/.claude/hooks/post_commit_doc.sh \
   plugins/sdlc/skills/scaffolding-sdlc/templates/claude-hooks/post_commit_doc.sh
```

Then verify the copied file contains the re-amend guard line `grep -qE '^docs/[0-9]{4}-` and does NOT contain `tool_input.command`.

- [ ] **Step 4: Create `settings-hooks.json`** (snippet to merge into a repo's `.claude/settings.json`):

```json
{
  "Stop": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "bash .claude/hooks/post_commit_doc.sh",
          "statusMessage": "Documenting commit..."
        }
      ]
    }
  ]
}
```

- [ ] **Step 5: Create `README.md`**:

```markdown
# claude-hooks/post_commit_doc.sh

A **Claude Code `Stop` hook** (not a git hook). The Claude Code harness runs it
when the agent finishes responding — so it can read `session_id` and amend the
commit. Git never invokes it; it only fires when Claude commits.

**Install:** copy `post_commit_doc.sh` into the repo's `.claude/hooks/` and merge
`settings-hooks.json` into `.claude/settings.json`. The command path is relative
(`bash .claude/hooks/post_commit_doc.sh`).

**Behavior:** after Claude commits, generates `docs/YYYY-MM-DD-HHmm_<slug>.md`
from the commit subject/body (+ optional session summary) and amends it into the
commit. Skips doc-only commits and commits that already contain a generated doc.

**Known quirk:** the generated doc records the pre-amend short hash.
```

- [ ] **Step 6: Run tests to verify they pass**

Run Step 1 (both PASS lines + `jq -e '.Stop'` succeeds). Then run the smoke test in a throwaway repo:

```bash
TMP=$(mktemp -d); cd "$TMP"; git init -q; git config user.email t@t.co; git config user.name t
echo code > app.py; git add app.py; git commit -qm "Add feature

body."
printf '{"session_id":"x"}' | bash "$OLDPWD/plugins/sdlc/skills/scaffolding-sdlc/templates/claude-hooks/post_commit_doc.sh"
ls docs/*.md && echo "DOC GENERATED"
cd "$OLDPWD"; rm -rf "$TMP"
```
Expected: `DOC GENERATED` and exactly one `docs/2026-*.md`.

- [ ] **Step 7: Commit**

```bash
git add plugins/sdlc/skills/scaffolding-sdlc/templates/claude-hooks
git commit -m "$(cat <<'EOF'
Add Claude commit-doc Stop hook template

Logic: Ship the fixed post_commit_doc.sh (Stop-hook payload, no
tool_input.command guard) plus a settings snippet and README so scaffolded
repos get working commit documentation.

Caveats/assumptions:
- Copied from the repaired global hook; re-amend guard prevents loops.
EOF
)"
```

---

### Task 9: Deterministic CI workflows (ci.yml, security.yml, dependabot.yml)

**Files:**
- Create: `.../templates/github/workflows/ci.yml`
- Create: `.../templates/github/workflows/security.yml`
- Create: `.../templates/github/dependabot.yml`

**Interfaces:**
- Produces: the deterministic PR gates. `ci.yml` detects stack via lockfiles and runs lint/typecheck/unit/e2e; `security.yml` runs gitleaks + dependency audit + Semgrep; `dependabot.yml` configures npm + pip updates.

- [ ] **Step 1: Write the failing test**

```bash
W=plugins/sdlc/skills/scaffolding-sdlc/templates/github/workflows
test -f "$W/ci.yml" && test -f "$W/security.yml" && test -f plugins/sdlc/skills/scaffolding-sdlc/templates/github/dependabot.yml
actionlint "$W/ci.yml" "$W/security.yml"
```

- [ ] **Step 2: Run it to verify it fails**

Run Step 1. Expected: FAIL (absent).

- [ ] **Step 3: Create `ci.yml`** (polyglot, graceful no-op pattern from translation's `ci.yml`):

```yaml
name: CI

on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
  push:
    branches: [main]

jobs:
  node:
    runs-on: ubuntu-latest
    permissions: { contents: read }
    steps:
      - uses: actions/checkout@v5
      - id: detect
        run: |
          if [ -f package-lock.json ]; then echo "present=true" >> "$GITHUB_OUTPUT";
          else echo "present=false" >> "$GITHUB_OUTPUT"; echo "::notice::No package-lock.json; skipping Node jobs."; fi
      - if: steps.detect.outputs.present == 'true'
        uses: actions/setup-node@v5
        with: { node-version: 20, cache: npm }
      - if: steps.detect.outputs.present == 'true'
        run: npm ci
      - if: steps.detect.outputs.present == 'true'
        run: make lint
      - if: steps.detect.outputs.present == 'true'
        run: make typecheck
      - if: steps.detect.outputs.present == 'true'
        run: make test

  python:
    runs-on: ubuntu-latest
    permissions: { contents: read }
    steps:
      - uses: actions/checkout@v5
      - id: detect
        run: |
          if [ -f pyproject.toml ]; then echo "present=true" >> "$GITHUB_OUTPUT";
          else echo "present=false" >> "$GITHUB_OUTPUT"; echo "::notice::No pyproject.toml; skipping Python jobs."; fi
      - if: steps.detect.outputs.present == 'true'
        uses: astral-sh/setup-uv@v5
      - if: steps.detect.outputs.present == 'true'
        run: make check
      - if: steps.detect.outputs.present == 'true'
        run: make typecheck
      - if: steps.detect.outputs.present == 'true'
        run: make test-python

  e2e:
    runs-on: ubuntu-latest
    permissions: { contents: read }
    steps:
      - uses: actions/checkout@v5
      - id: detect
        run: |
          if [ -d frontend ] || ls playwright.config.* >/dev/null 2>&1; then echo "present=true" >> "$GITHUB_OUTPUT";
          else echo "present=false" >> "$GITHUB_OUTPUT"; echo "::notice::No frontend/playwright config; skipping e2e."; fi
      - if: steps.detect.outputs.present == 'true'
        uses: actions/setup-node@v5
        with: { node-version: 20, cache: npm }
      - if: steps.detect.outputs.present == 'true'
        run: npm ci
      - if: steps.detect.outputs.present == 'true'
        run: npx playwright install --with-deps
      - if: steps.detect.outputs.present == 'true'
        run: make test-e2e
```

- [ ] **Step 4: Create `security.yml`**:

```yaml
name: Security

on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
  schedule:
    - cron: "0 6 * * 1"

jobs:
  secrets:
    runs-on: ubuntu-latest
    permissions: { contents: read }
    steps:
      - uses: actions/checkout@v5
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  dependencies:
    runs-on: ubuntu-latest
    permissions: { contents: read }
    steps:
      - uses: actions/checkout@v5
      - name: npm audit
        run: '[ -f package-lock.json ] && npm audit --audit-level=high || echo "no package-lock.json; skipping npm audit"'
      - name: pip-audit
        run: |
          if [ -f pyproject.toml ]; then
            pipx run pip-audit || echo "pip-audit reported findings"
          else echo "no pyproject.toml; skipping pip-audit"; fi

  semgrep:
    runs-on: ubuntu-latest
    permissions: { contents: read }
    container: { image: returntocorp/semgrep }
    steps:
      - uses: actions/checkout@v5
      - run: semgrep ci || true
        env:
          SEMGREP_APP_TOKEN: ${{ secrets.SEMGREP_APP_TOKEN }}
```

- [ ] **Step 5: Create `dependabot.yml`**:

```yaml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule: { interval: "weekly" }
    labels: ["dependencies"]
  - package-ecosystem: "pip"
    directory: "/"
    schedule: { interval: "weekly" }
    labels: ["dependencies"]
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule: { interval: "weekly" }
    labels: ["dependencies"]
```

- [ ] **Step 6: Run tests to verify they pass**

Run Step 1. Expected: `actionlint` reports no errors on `ci.yml` and `security.yml`. Validate `dependabot.yml`: `python3 -c "import yaml;yaml.safe_load(open('plugins/sdlc/skills/scaffolding-sdlc/templates/github/dependabot.yml'))"`.

- [ ] **Step 7: Commit**

```bash
git add plugins/sdlc/skills/scaffolding-sdlc/templates/github/workflows/ci.yml \
        plugins/sdlc/skills/scaffolding-sdlc/templates/github/workflows/security.yml \
        plugins/sdlc/skills/scaffolding-sdlc/templates/github/dependabot.yml
git commit -m "$(cat <<'EOF'
Add deterministic CI + security workflows

Logic: ci.yml runs polyglot lint/typecheck/unit/e2e gates that no-op when a
stack is absent; security.yml adds gitleaks + dep audit + Semgrep; Dependabot
covers npm/pip/actions. Gates call Makefile targets so local == CI.

Alternatives considered:
- CodeQL: dropped per spec; Semgrep + Claude /security-review cover SAST.

Caveats/assumptions:
- Semgrep/pip-audit tolerate findings (|| true) so the deterministic gate
  reports without hard-failing; tighten per-repo as desired.
EOF
)"
```

---

### Task 10: Event-driven workflows (Claude automation, PR-status labels, PR rebase)

**Files:**
- Create: `.../templates/github/workflows/code-review.yml`
- Create: `.../templates/github/workflows/claude.yml`
- Create: `.../templates/github/workflows/claude-comment-triage.yml`
- Create: `.../templates/github/workflows/pr-status-labels.yml`
- Create: `.../templates/github/workflows/pr-rebase.yml`

**Interfaces:**
- Produces: the event-driven automation workflows. `code-review.yml`, `claude.yml`, and `claude-comment-triage.yml` are copied from the translation `comment-triage-workflow` branch with the `no-automation` label substitution; `pr-status-labels.yml` and `pr-rebase.yml` are net-new.
- `pr-rebase.yml` keeps open PRs current: on every push to `main` (and via manual dispatch) it rebases each behind, same-repo, non-opted-out PR branch onto `main` and force-pushes with lease; on conflicts it aborts, adds `needs-rebase`, and comments.

- [ ] **Step 1: Write the failing test**

```bash
W=plugins/sdlc/skills/scaffolding-sdlc/templates/github/workflows
for f in code-review.yml claude.yml claude-comment-triage.yml pr-status-labels.yml pr-rebase.yml; do test -f "$W/$f" || echo "MISSING $f"; done
actionlint "$W/code-review.yml" "$W/claude.yml" "$W/claude-comment-triage.yml" "$W/pr-status-labels.yml" "$W/pr-rebase.yml"
grep -q 'cssherry-wp/claude-starter' "$W/claude-comment-triage.yml"
grep -q 'no-automation' "$W/claude-comment-triage.yml" && ! grep -q 'do-not-respond' "$W/claude-comment-triage.yml"
grep -q 'force-with-lease' "$W/pr-rebase.yml" && grep -q 'needs-rebase' "$W/pr-rebase.yml"
grep -q 'create-github-app-token' "$W/pr-rebase.yml" && grep -q 'secrets.REBASE_TOKEN' "$W/pr-rebase.yml"
```

- [ ] **Step 2: Run it to verify it fails**

Run Step 1. Expected: MISSING lines.

- [ ] **Step 3: Copy `code-review.yml`, `claude.yml`, `claude-comment-triage.yml` from the source branch**

```bash
W=plugins/sdlc/skills/scaffolding-sdlc/templates/github/workflows
SRC=/Users/sherryzhou/code/translation_sdlc_demo
git -C "$SRC" show comment-triage-workflow:.github/workflows/code-review.yml > "$W/code-review.yml"
git -C "$SRC" show comment-triage-workflow:.github/workflows/claude.yml > "$W/claude.yml"
git -C "$SRC" show comment-triage-workflow:.github/workflows/claude-comment-triage.yml > "$W/claude-comment-triage.yml"
```

- [ ] **Step 4: Substitute the label rename in `claude-comment-triage.yml`**

Replace every `do-not-respond` with `no-automation` (the guard conditions and the prompt's housekeeping text). After this step, `grep -c do-not-respond "$W/claude-comment-triage.yml"` must be `0`.

- [ ] **Step 5: Create `pr-status-labels.yml`** (net-new):

```yaml
name: PR Status Labels

on:
  workflow_run:
    workflows: ["CI"]
    types: [requested, completed]

permissions:
  pull-requests: write
  issues: write

jobs:
  label:
    if: github.event.workflow_run.event == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - name: Resolve PR number
        id: pr
        env: { GH_TOKEN: "${{ secrets.GITHUB_TOKEN }}" }
        run: |
          NUM=$(gh api "repos/${{ github.repository }}/commits/${{ github.event.workflow_run.head_sha }}/pulls" \
            --jq '.[0].number' 2>/dev/null || echo "")
          echo "number=$NUM" >> "$GITHUB_OUTPUT"
      - name: Apply status label
        if: steps.pr.outputs.number != ''
        env: { GH_TOKEN: "${{ secrets.GITHUB_TOKEN }}" }
        run: |
          PR=${{ steps.pr.outputs.number }}
          gh pr edit "$PR" --remove-label check-in-progress --remove-label check-pass --remove-label check-fail || true
          if [ "${{ github.event.action }}" = "requested" ]; then
            gh pr edit "$PR" --add-label check-in-progress
          elif [ "${{ github.event.workflow_run.conclusion }}" = "success" ]; then
            gh pr edit "$PR" --add-label check-pass
          else
            gh pr edit "$PR" --add-label check-fail
          fi
```

- [ ] **Step 6: Create `pr-rebase.yml`** (net-new):

Auth: prefer a **GitHub App** installation token (not tied to a user, short-lived), fall back to a fine-grained **PAT** (`REBASE_TOKEN`), then `GITHUB_TOKEN` as last resort. Only the first two re-trigger CI on the rebased commit; `GITHUB_TOKEN` pushes do not. The App step uses `continue-on-error` so a repo without the App secrets degrades to the PAT/`GITHUB_TOKEN` fallback automatically.

```yaml
name: PR Rebase

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

jobs:
  rebase:
    runs-on: ubuntu-latest
    steps:
      # Preferred: GitHub App installation token. Falls back to a fine-grained
      # PAT (REBASE_TOKEN), then GITHUB_TOKEN (which does NOT re-trigger CI).
      - name: Mint GitHub App token (preferred)
        id: app-token
        continue-on-error: true
        uses: actions/create-github-app-token@v1
        with:
          app-id: ${{ secrets.REBASE_APP_ID }}
          private-key: ${{ secrets.REBASE_APP_PRIVATE_KEY }}
      - uses: actions/checkout@v5
        with:
          fetch-depth: 0
          token: ${{ steps.app-token.outputs.token || secrets.REBASE_TOKEN || secrets.GITHUB_TOKEN }}
      - name: Rebase behind PRs onto main
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token || secrets.REBASE_TOKEN || secrets.GITHUB_TOKEN }}
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git fetch origin main
          # Open, same-repo PRs based on main, not opted out via no-automation.
          gh pr list --state open --base main \
            --json number,headRefName,isCrossRepository,labels \
            --jq '.[] | select(.isCrossRepository==false)
                       | select((.labels // []) | any(.name=="no-automation") | not)
                       | [.number, .headRefName] | @tsv' \
          | while IFS="$(printf '\t')" read -r NUM BRANCH; do
              echo "::group::PR #$NUM ($BRANCH)"
              git fetch origin "$BRANCH"
              if git merge-base --is-ancestor origin/main "origin/$BRANCH"; then
                echo "#$NUM already contains main; skipping."
                gh pr edit "$NUM" --remove-label needs-rebase || true
                echo "::endgroup::"; continue
              fi
              git checkout -B "$BRANCH" "origin/$BRANCH"
              if git rebase origin/main; then
                if git push --force-with-lease origin "$BRANCH"; then
                  gh pr edit "$NUM" --remove-label needs-rebase || true
                  echo "rebased #$NUM"
                else
                  echo "push rejected (branch moved) for #$NUM"
                fi
              else
                git rebase --abort
                gh pr edit "$NUM" --add-label needs-rebase || true
                gh pr comment "$NUM" --body "Automatic rebase onto \`main\` hit conflicts; please rebase manually. <!-- pr-rebase -->"
              fi
              echo "::endgroup::"
            done
```

- [ ] **Step 7: Run tests to verify they pass**

Run Step 1. Expected: no MISSING; `actionlint` clean on all five; `cssherry-wp/claude-starter` present; `no-automation` present and `do-not-respond` absent in the triage workflow; `force-with-lease`, `needs-rebase`, `create-github-app-token`, and `secrets.REBASE_TOKEN` all present in `pr-rebase.yml`.

- [ ] **Step 8: Commit**

```bash
git add plugins/sdlc/skills/scaffolding-sdlc/templates/github/workflows/code-review.yml \
        plugins/sdlc/skills/scaffolding-sdlc/templates/github/workflows/claude.yml \
        plugins/sdlc/skills/scaffolding-sdlc/templates/github/workflows/claude-comment-triage.yml \
        plugins/sdlc/skills/scaffolding-sdlc/templates/github/workflows/pr-status-labels.yml \
        plugins/sdlc/skills/scaffolding-sdlc/templates/github/workflows/pr-rebase.yml
git commit -m "$(cat <<'EOF'
Add event-driven workflows (Claude, PR-status, PR-rebase)

Logic: Fuse the mature comment-triage-workflow branch workflows (code+security
review, @claude responder, autonomous comment triage); add net-new
pr-status-labels (keyed off CI workflow_run) and pr-rebase (auto-rebase behind
PRs onto main, label+comment on conflict).

Caveats/assumptions:
- Marketplace hardcoded to cssherry-wp/claude-starter per spec.
- do-not-respond renamed to no-automation throughout.
- pr-status-labels resolves PR via head_sha; single-PR-per-sha assumption.
- pr-rebase only touches same-repo branches (cannot push to forks) and skips
  no-automation PRs. Auth prefers a GitHub App token, falls back to a
  fine-grained PAT (REBASE_TOKEN), then GITHUB_TOKEN; only the first two
  re-trigger CI on the rebased commit. App/PAT secrets are a manual prereq.
EOF
)"
```

---

### Task 11: `references/security-tooling.md`

**Files:**
- Create: `.../references/security-tooling.md`

**Interfaces:**
- Produces: a reference doc the SKILL.md links to (not inlined), describing each scanner, its config, required secrets, and tradeoffs.

- [ ] **Step 1: Write the failing test**

```bash
R=plugins/sdlc/skills/scaffolding-sdlc/references/security-tooling.md
test -f "$R" && grep -qi gitleaks "$R" && grep -qi semgrep "$R" && grep -qi dependabot "$R" && grep -qi 'security-review' "$R"
```

- [ ] **Step 2: Run it to verify it fails**

Run Step 1. Expected: FAIL (absent).

- [ ] **Step 3: Write the reference**

```markdown
# Security tooling reference

The skill wires five complementary security layers. Enable per repo; the
playbook asks the user to confirm.

| Layer | Tool | Catches | Where | Secret needed |
|-------|------|---------|-------|---------------|
| Secrets | gitleaks | committed credentials | pre-commit + `security.yml` | none (uses GITHUB_TOKEN) |
| Dependencies (CVEs) | npm audit / pip-audit | known-vulnerable deps | `security.yml` | none |
| Dependency updates | Dependabot | outdated deps (auto-PRs) | `dependabot.yml` | none |
| SAST (patterns) | Semgrep | insecure code patterns | `security.yml` | `SEMGREP_APP_TOKEN` (optional) |
| SAST (semantic) | Claude `/security-review` | logic/semantic security issues | `code-review.yml` | `CLAUDE_CODE_OAUTH_TOKEN` |

## Notes
- **gitleaks** must be installed locally for the pre-commit scan
  (`brew install gitleaks`); the CI job needs no install.
- **Semgrep** runs `semgrep ci`; without `SEMGREP_APP_TOKEN` it uses the open
  rulesets. The gate tolerates findings (`|| true`) — tighten per repo.
- **Claude `/security-review`** is semantic and complements the deterministic
  scanners; it skips `[autofix]` commits to avoid re-reviewing auto-fixes.
- **CodeQL** is intentionally excluded. To add it later, create a separate
  `codeql.yml`; it does not replace any layer above.
```

- [ ] **Step 4: Run tests to verify they pass**

Run Step 1. Expected: success.

- [ ] **Step 5: Commit**

```bash
git add plugins/sdlc/skills/scaffolding-sdlc/references/security-tooling.md
git commit -m "$(cat <<'EOF'
Add security-tooling reference

Logic: Keep per-scanner detail out of SKILL.md (token budget) and in a
linked reference covering tools, secrets, and tradeoffs.
EOF
)"
```

---

### Task 12: Author SKILL.md (the interactive playbook)

**Files:**
- Modify: `plugins/sdlc/skills/scaffolding-sdlc/SKILL.md` (replace stub)

**Interfaces:**
- Consumes: `scripts/detect-stack.sh`, `scripts/ensure-labels.sh`, all `templates/*`, `references/security-tooling.md`.
- Produces: the orchestration playbook an agent follows to scaffold a repo.

- [ ] **Step 1: Write the failing test**

```bash
S=plugins/sdlc/skills/scaffolding-sdlc/SKILL.md
python3 -c "import re,sys;t=open('$S').read();m=re.match(r'^---\n.*?\n---\n',t,re.S);sys.exit(0 if m and 'description:' in m.group(0) else 1)"
grep -qi 'detect' "$S" && grep -Eqi 'never overwrite|do not overwrite|do not clobber' "$S" \
  && grep -q 'ensure-labels.sh' "$S" && grep -q 'detect-stack.sh' "$S" \
  && grep -qi 'no-automation' "$S" && grep -q 'CLAUDE_CODE_OAUTH_TOKEN' "$S"
```

- [ ] **Step 2: Run it to verify it fails**

Run Step 1. Expected: FAIL (stub lacks these references).

- [ ] **Step 3: Write the full SKILL.md**

Replace the file with the playbook below (keep the frontmatter `name`/`description` from Task 1):

````markdown
---
name: scaffolding-sdlc
description: Use when starting a new repo or adding SDLC automation to an existing one — sets up lint, unit tests, Playwright e2e, security scanning, Dependabot, PR-status labels, pre-commit hooks, and Claude PR automation that run on every PR. Use when a repo lacks CI gates, has no pre-commit checks, or needs standardized GitHub Actions.
---

# Scaffolding SDLC

## Overview

Interactively bootstrap standardized SDLC automation into a repo: a local task
runner (Makefile), a git pre-commit hook, a Claude commit-doc Stop hook, GitHub
Actions PR gates (lint, typecheck, unit, Playwright e2e, security), Dependabot,
PR-status labels, and four Claude PR-automation workflows.

**Core principle:** local == CI (both call the same Makefile targets), and never
clobber existing files — detect, diff, ask, merge.

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

1. **Detect & report.** Run `scripts/detect-stack.sh` in the target repo. Also
   inspect existing `.github/`, `Makefile`, hooks, and labels (`gh label list`),
   and note the repo's conventions: package manager (pip vs uv), config-file
   style (standalone `ruff.toml`/`pytest.ini` vs `[tool.*]`), project
   subdirectory (manifests under `app/`, `app/frontend/`, etc.), and existing
   frontend linter. Report what exists vs. what is missing. **Never overwrite
   existing files silently** — for any file that already exists, show the diff
   and ask before changing it. **Adapt, don't impose:** where the repo already
   has a convention, conform to it (e.g. add `pip-audit` for a pip repo, wire CI
   `working-directory` to the project subdir, call the repo's existing `make`
   targets) instead of forcing the template's defaults.

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

4. **git pre-commit hook.** Copy `templates/git-hooks/pre-commit` →
   `.sdlc-hooks/pre-commit`, then run `make install-hooks` to symlink it.

5. **Claude commit-doc hook.** Copy `templates/claude-hooks/post_commit_doc.sh`
   → `.claude/hooks/`, and merge `templates/claude-hooks/settings-hooks.json`
   into `.claude/settings.json` (append to any existing `Stop` array; do not
   replace it). Docs land in `docs/`.

6. **GitHub Actions.** Copy `templates/github/workflows/*.yml` →
   `.github/workflows/` (gates `ci.yml`/`security.yml`, the Claude automation
   trio, `pr-status-labels.yml`, and `pr-rebase.yml`) and
   `templates/github/dependabot.yml` → `.github/dependabot.yml`. Skip any
   workflow the user opted out of (e.g. no Semgrep → leave the `semgrep` job out
   of `security.yml`). `pr-rebase.yml` auto-rebases behind PRs onto `main` and
   force-pushes with lease; remind the user to add the GitHub App (preferred) or
   `REBASE_TOKEN` PAT secrets so rebased pushes re-trigger CI (see Prerequisites).

7. **Ensure labels.** Run `scripts/ensure-labels.sh` (idempotent). Creates
   `check-in-progress`, `check-pass`, `check-fail`, `question`, `no-automation`,
   `dependencies`, `security`, `needs-rebase`.

8. **Verify & summarize.** Run `make check` and `make test` locally and report
   results. Summarize what was created/changed and list manual follow-ups: add
   the repo secrets above, and (recommended) enable branch protection requiring
   the CI checks.

## Key facts

- `claude-comment-triage.yml` depends on the `github-pr-review@claude-starter`
  plugin and hardcodes the marketplace `cssherry-wp/claude-starter`.
- `[autofix]` coordination: triage commits are `[autofix]`-prefixed and signed
  `<!-- claude-autofix -->`; `code-review.yml` skips them.
- The two hook types differ: `pre-commit` is a git hook (git fires it);
  `post_commit_doc.sh` is a Claude Code Stop hook (the harness fires it). See
  each template's README.

## Common mistakes

- Overwriting an existing `package.json`/`pyproject.toml`/`.claude/settings.json`
  instead of merging — always merge.
- Forgetting the `CLAUDE_CODE_OAUTH_TOKEN` secret — the four Claude workflows
  silently no-op or fail without it.
- Scaffolding the Playwright `e2e` job for a backend-only repo — it is for
  frontends; the CI job already no-ops, but don't promise e2e where there's no UI.
````

- [ ] **Step 4: Run tests to verify they pass**

Run Step 1. Expected: success (frontmatter valid; all required references present). Check word count is reasonable: `wc -w "$S"` (target < 700 words for the body).

- [ ] **Step 5: Commit**

```bash
git add plugins/sdlc/skills/scaffolding-sdlc/SKILL.md
git commit -m "$(cat <<'EOF'
Author scaffolding-sdlc playbook

Logic: Replace the stub with the 8-step interactive orchestration that ties
together detect-stack, the stack templates, both hook types, the GitHub
Actions suite, and ensure-labels — with merge-don't-clobber safety rules.

Caveats/assumptions:
- Heavy per-scanner detail lives in references/security-tooling.md to keep
  the always-loaded SKILL.md lean.
EOF
)"
```

---

### Task 13: Skill TDD — RED baseline + GREEN verification (writing-skills)

**Files:**
- Create (temporary, not committed): scratch scenario notes under `/tmp`.
- Modify if needed: `SKILL.md` (close loopholes found in testing).

**Interfaces:**
- Consumes: the complete skill from Tasks 1–12.
- Produces: evidence the skill works on real repos; any SKILL.md refinements.

REQUIRED BACKGROUND: Use superpowers:writing-skills (testing section) and superpowers:test-driven-development. This is the Iron Law applied to the skill: observe baseline failure before trusting the skill.

- [ ] **Step 1: RED — baseline without the skill**

Dispatch a subagent (general-purpose) WITHOUT mentioning this skill, against a fresh throwaway repo:
> "Set up SDLC automation (lint, unit tests, Playwright e2e, security checks) that runs on every PR for this repo."
Provide a throwaway TS repo (`npm init -y` + a `tsconfig.json`). Record verbatim: what files it creates, what it omits (labels? pre-commit? security? commit-doc hook?), and any inconsistencies. Save notes to `/tmp/sdlc-baseline.md`.

- [ ] **Step 2: Confirm the baseline is incomplete**

Expected: the baseline subagent produces partial/inconsistent setup (e.g. a single CI workflow, no pre-commit, no labels, no security suite, no commit-doc hook). This is the failing test that justifies the skill.

- [ ] **Step 3: GREEN — run the skill on three scenarios**

For each, dispatch a subagent told to use the `scaffolding-sdlc` skill and follow it exactly:
- (a) Fresh TS repo (`npm init -y`).
- (b) A copy of the fullstack repo: `cp -r /Users/sherryzhou/code/structured_data_demo /tmp/sdlc-fullstack && rm -rf /tmp/sdlc-fullstack/.git && git -C /tmp/sdlc-fullstack init -q`.
- (c) A repo with partial setup (TS repo that already has a `biome.json` and a `.github/workflows/ci.yml`) — verify the skill does NOT overwrite them and merges/asks instead.

- [ ] **Step 4: Verify GREEN outcomes**

For each scenario confirm: correct stack detected; Makefile + configs present; `git-hooks/pre-commit` installed; `post_commit_doc.sh` wired into `.claude/settings.json`; all `.github/workflows/*` present and `actionlint`-clean; `dependabot.yml` present; labels ensured (or the `gh` command emitted); scenario (c) preserved the pre-existing `biome.json` and `ci.yml`. Record results in `/tmp/sdlc-green.md`.

- [ ] **Step 5: Close loopholes**

If any scenario showed the agent overwriting files, skipping labels, or misusing the hooks, add an explicit counter to SKILL.md's "Common mistakes" / safety rules and re-run that scenario. Repeat until all three pass.

- [ ] **Step 6: Commit any SKILL.md refinements**

```bash
git add plugins/sdlc/skills/scaffolding-sdlc/SKILL.md
git commit -m "$(cat <<'EOF'
Refine scaffolding-sdlc from RED/GREEN testing

Logic: Application-scenario testing (fresh TS, fullstack, partial repo)
surfaced <gaps>; added explicit counters so the skill scaffolds completely
without clobbering existing files.

Caveats/assumptions:
- Scenarios run against throwaway repos; live gh label calls require auth.
EOF
)"
```

(If no refinements were needed, skip the commit and note that baseline was incomplete and all three GREEN scenarios passed unchanged.)

---

### Task 14: End-to-end integration check + finalize

**Files:**
- Modify: `README.md` (add the `sdlc` plugin to the marketplace listing).

**Interfaces:**
- Consumes: everything. Produces: a validated, documented plugin ready to merge.

- [ ] **Step 1: Write the failing test**

```bash
grep -qi 'scaffolding-sdlc\|sdlc plugin' README.md && echo PASS || echo FAIL
```

- [ ] **Step 2: Run it to verify it fails**

Run Step 1. Expected: FAIL.

- [ ] **Step 3: Full validation sweep**

```bash
SK=plugins/sdlc/skills/scaffolding-sdlc
shellcheck $SK/scripts/*.sh $SK/templates/claude-hooks/post_commit_doc.sh
shellcheck -s sh $SK/templates/git-hooks/pre-commit
actionlint $SK/templates/github/workflows/*.yml
python3 -c "import json;json.load(open('.claude-plugin/marketplace.json'));json.load(open('plugins/sdlc/.claude-plugin/plugin.json'))"
python3 -c "import yaml,glob;[yaml.safe_load(open(f)) for f in glob.glob('$SK/templates/github/**/*.yml',recursive=True)]"
```
Expected: all clean.

- [ ] **Step 4: Update `README.md`**

Add the `sdlc` plugin to the plugin listing section (match the existing format used for `standards`/`workflows`/`superpowers-team`): one row/bullet naming the `sdlc` plugin and its `scaffolding-sdlc` skill.

- [ ] **Step 5: Run tests to verify they pass**

Run Step 1 (PASS) and re-run Step 3 (all clean).

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
Document sdlc plugin in README

Logic: Surface the new scaffolding-sdlc skill in the marketplace README so
the team can discover and enable it.
EOF
)"
```

- [ ] **Step 7: Finish the branch**

REQUIRED SUB-SKILL: Use superpowers:finishing-a-development-branch to choose merge/PR/cleanup for branch `sdlc-scaffolding-skill`.

---

## Self-Review

**Spec coverage:**
- Interactive detect→ask→scaffold flow → Tasks 2, 12.
- TS / Python / Fullstack stacks → Tasks 4, 5, 6.
- React minimal-vs-full at runtime → Task 6 + SKILL.md Step 2 (Task 12).
- Local Makefile (local==CI) → Tasks 4–6, used by Task 9 gates.
- git pre-commit (gitleaks) → Task 7.
- Claude commit-doc Stop hook (fixed) → Task 8.
- ci.yml gates (lint/typecheck/unit/playwright) → Task 9.
- security.yml (gitleaks/dep-audit/Semgrep) + Dependabot → Task 9.
- code-review.yml (Claude code+security), claude.yml, claude-comment-triage.yml → Task 10.
- pr-status-labels.yml + label set incl. `no-automation`, `needs-rebase` → Tasks 3, 10.
- pr-rebase.yml (auto-rebase behind PRs onto main; conflict → `needs-rebase` + comment) → Task 10.
- Adapt-don't-impose (pip/uv, config style, project subdir, FE linter, existing Makefile targets) → Tasks 1-constraints + 12 (Detect & report / runtime adaptation).
- `docs/` convention, no-clobber, idempotent labels → Tasks 8, 12, 3.
- Marketplace hardcoded `cssherry-wp/claude-starter` → Task 10.
- CodeQL excluded; both security layers → Tasks 9, 11.
- writing-skills TDD (RED/GREEN) → Task 13.
- README/marketplace registration → Tasks 1, 14.

No gaps found.

**Placeholder scan:** No TBD/TODO. Verbatim-copy steps give exact source paths + post-copy assertions; net-new files have full content.

**Type consistency:** Makefile target names (`check`, `typecheck`, `test`, `test-python`, `test-e2e`, `install-hooks`, `lint`) are consistent across Tasks 4/5/6 and referenced identically in `ci.yml` (Task 9). The 8 managed label names match across Tasks 3, 10, 12 (including `needs-rebase`, written by `pr-rebase.yml` and created by `ensure-labels.sh`). Hook install path `.sdlc-hooks/pre-commit` consistent across Tasks 4/5/6/12. `no-automation` is the single opt-out label used by both `claude-comment-triage.yml` and `pr-rebase.yml`.
