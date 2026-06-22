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
