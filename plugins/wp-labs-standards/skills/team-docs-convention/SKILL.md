---
name: team-docs-convention
description: Team conventions for where specs and plans are saved and for reviewing worktree changes. Use when brainstorming a spec, writing an implementation plan, referencing spec/plan files, or finishing work in a git worktree — overrides any default doc path (including superpowers' docs/superpowers/... paths).
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

## Worktree review

When working in a git worktree, once the work is done (all files for the task generated and
ready), open the worktree repo folder in VSCode so it can be reviewed:

```bash
code "$(git rev-parse --show-toplevel)"
```

Do this once at completion, not after every file edit. If the `code` command is unavailable,
report the worktree path and tell the user to open it manually.
