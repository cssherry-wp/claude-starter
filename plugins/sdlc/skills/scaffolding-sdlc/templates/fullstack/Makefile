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
