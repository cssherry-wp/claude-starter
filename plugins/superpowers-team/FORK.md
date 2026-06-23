# superpowers-team — fork notes

This is a vendored fork of [superpowers](https://github.com/obra/superpowers), trimmed to the
plugin essentials and customized with the team docs-path convention.

## Upstream base

- Source: `obra/superpowers`
- Version: **6.0.3**
- Base commit: **`896224c4b1879920ab573417e68fd51d2ccc9072`**
- License: MIT (see `LICENSE`)

## What diverges from upstream

1. **Docs-path convention** applied to the skill text:
   - `docs/superpowers/specs/...` → `docs/01-specs/YYYY-MM-DD-HHmm-<name-of-spec>.md`
   - `docs/superpowers/plans/...` → `docs/02-plans/YYYY-MM-DD-HHmm-<name-of-plan>.md`
2. **Slimmed to plugin essentials** — kept `.claude-plugin/`, `skills/`, `hooks/`, `LICENSE`,
   `README.md`; removed upstream dev/CI/test files, the upstream project's own `docs/`, and
   other-harness directories.

## Why a fork (vs the overlay)

The default delivery is the lightweight `team-docs-convention` skill in the `standards` plugin.
This fork bakes the paths into the skill text. Enable **either** stock superpowers **or** this fork
— never both (they define the same skill names).

## How to refresh against a new upstream release

Run `scripts/refresh-superpowers-fork.sh` (or let the weekly
`.github/workflows/refresh-superpowers-fork.yml` do it and open a PR). The script re-copies the
plugin essentials, re-applies the path convention, bumps the version, and updates this file.
