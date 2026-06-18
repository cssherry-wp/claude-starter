---
name: team-docs-convention
description: Team convention for where specs and plans are saved. Use when brainstorming a spec, writing an implementation plan, or referencing spec/plan files — overrides any default doc path (including superpowers' docs/superpowers/... paths).
---

# Team Docs Convention

When creating or referencing design specs and implementation plans, use these paths and
naming — they **override** any default a skill suggests (e.g. superpowers' `docs/superpowers/specs/`
and `docs/superpowers/plans/`):

- **Specs:** `docs/01-specs/YYYY-MM-DD-HHmm-<name-of-spec>.md`
- **Plans:** `docs/02-plans/YYYY-MM-DD-HHmm-<name-of-plan>.md`

Rules:
- Use a 24-hour `HHmm` timestamp in the filename so multiple docs created the same day sort correctly.
- `<name-of-spec>` / `<name-of-plan>` is a short kebab-case slug.
- Create `docs/01-specs/` or `docs/02-plans/` if it doesn't exist; commit the doc to git.

If you are following the superpowers brainstorming or writing-plans skills, substitute these
paths wherever they reference `docs/superpowers/specs/` or `docs/superpowers/plans/`.
