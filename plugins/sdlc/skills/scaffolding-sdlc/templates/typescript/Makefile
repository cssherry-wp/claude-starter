# TypeScript SDLC targets — scaffolded by scaffolding-sdlc.
.PHONY: install lint format check typecheck test test-e2e install-hooks

install:
	# `npm install` (not `npm ci`): a freshly scaffolded repo has no
	# package-lock.json yet; this creates it. CI uses `npm ci` off the
	# committed lockfile.
	npm install

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
