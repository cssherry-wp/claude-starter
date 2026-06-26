---
name: team-docs-convention
description: Team convention for where specs and plans are saved. Use when brainstorming a spec, writing an implementation plan, or referencing spec/plan files — overrides any default doc path (including superpowers' docs/superpowers/... paths).
---

# Team Docs Convention

When creating or referencing design specs and implementation plans, use these paths and
naming — they **override** any default a skill suggests (e.g. superpowers' `docs/superpowers/specs/`
and `docs/superpowers/plans/`):

- **Specs:** `.superpowers/01-specs/YYYY-MM-DD-HHmm-<name-of-spec>.md`
- **Plans:** `.superpowers/02-plans/YYYY-MM-DD-HHmm-<name-of-plan>.md`

Rules:
- Use a 24-hour `HHmm` timestamp in the filename so multiple docs created the same day sort correctly.
- `<name-of-spec>` / `<name-of-plan>` is a short kebab-case slug.
- Create `.superpowers/01-specs/` or `.superpowers/02-plans/` if it doesn't exist; commit the doc to git.

If you are following the superpowers brainstorming or writing-plans skills, substitute these
paths wherever they reference `docs/superpowers/specs/` or `docs/superpowers/plans/`.

## Lifecycle: spec → issue → plan-comment → feature docs

These steps apply whether you use stock superpowers or the team fork:

1. **Spec → issue** (after the spec is approved): if the spec derives from an existing GitHub
   issue, append it as a comment (`gh issue comment <n> --body-file <spec>`). Otherwise ask
   `Create a GitHub tracking issue for this spec? (Y/n)` and on yes create it
   (`gh issue create --title "<slug>" --body-file <spec>`). Record `Tracking issue: <url>` in the
   spec and commit.
2. **Plan → comment** (after the plan is saved): read the spec's `Tracking issue:` line and post
   the plan as a comment (`gh issue comment <n> --body-file <plan>`). Skip if no issue is linked.
3. **Implementation → docs** (after implementation completes): write a task-oriented
   usage/adaptation guide for the feature into `docs/<kebab-name>.md` — a how-to guide, not a
   dated changelog.

If `gh` is missing or unauthenticated, report and continue; never block on it.
