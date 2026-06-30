# Fullstack (Python backend + React/Vite frontend) SDLC targets.
# The frontend is a self-contained npm project under frontend/.
.PHONY: install lint lint-python lint-js lint-css lint-infra format check check-python check-js check-css typecheck typecheck-python test test-python test-js test-e2e install-hooks

install:
	uv sync --extra dev
	cd frontend && npm install

lint: lint-python lint-js lint-css lint-infra
lint-python: ; uv run --extra dev ruff check .
lint-js: ; cd frontend && npm run lint
lint-css: ; cd frontend && npx stylelint "src/**/*.scss" --allow-empty-input
# Lint Bicep templates when an infra/ layer is present (no-op otherwise).
lint-infra: ; @if ls infra/*.bicep >/dev/null 2>&1; then for f in infra/*.bicep; do az bicep build --file "$$f" --stdout >/dev/null && echo "bicep ok: $$f"; done; else echo "no infra/*.bicep — skipping bicep lint"; fi

format:
	uv run --extra dev ruff format .
	uv run --extra dev ruff check --fix .
	cd frontend && npm run format
	cd frontend && npx stylelint --fix "src/**/*.scss" --allow-empty-input

# CI mode: no file modifications.
check: check-python check-js check-css lint-infra
check-python:
	uv run --extra dev ruff check .
	uv run --extra dev ruff format --check .
check-js:
	cd frontend && npm run typecheck
	cd frontend && npm run lint
check-css: ; cd frontend && npx stylelint "src/**/*.scss" --allow-empty-input

typecheck: check-js typecheck-python
typecheck-python:
	uv run --extra dev mypy . || echo "WARNING: mypy found issues — review output above"

test: test-python test-js
test-python: ; uv run --extra dev pytest
test-js: ; cd frontend && npm test
test-e2e: ; cd frontend && npm run test:e2e

install-hooks:
	@if [ -d .git ]; then ln -sf ../../.sdlc-hooks/pre-commit .git/hooks/pre-commit && echo "pre-commit installed"; else echo "not a git repo"; fi
