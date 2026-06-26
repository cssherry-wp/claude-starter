---
name: team-docs-convention
description: Team convention for where specs and plans are saved. Use when brainstorming a spec, writing an implementation plan, or referencing spec/plan files — overrides any default doc path (including superpowers' docs/superpowers/... paths).
---

# Team Docs Convention

When creating or referencing design specs and implementation plans, use these paths and
naming — they **override** any default a skill suggests (e.g. superpowers' `docs/superpowers/specs/`
and `docs/superpowers/plans/`):

- **Specs:** `<repo-top-level>/.superpowers/01-specs/YYYY-MM-DD-HHmm-<name-of-spec>.md`
- **Plans:** `<repo-top-level>/.superpowers/02-plans/YYYY-MM-DD-HHmm-<name-of-plan>.md`

Rules:
- Use a 24-hour `HHmm` timestamp in the filename so multiple docs created the same day sort correctly.
- `<name-of-spec>` / `<name-of-plan>` is a short kebab-case slug.
- **Always the top-level repository's `.superpowers/`.** When you are working in a git worktree,
  write to the **main working tree's** `.superpowers/`, not the worktree's — resolve it with
  `git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel`. This way every
  worktree shares one durable location and the docs survive the worktree being removed.
- Create `.superpowers/01-specs/` or `.superpowers/02-plans/` if it doesn't exist.
- **`.superpowers/` is git-ignored working space — do NOT commit specs or plans.** A committed
  `.superpowers/.gitignore` (`*` + `!.gitignore`) keeps the whole tree out of git on every branch
  and fresh clone. The GitHub tracking issue (see the lifecycle below) is their durable record.
  This overrides any "commit the design document / plan to git" step in the brainstorming or
  writing-plans skills.

If you are following the superpowers brainstorming or writing-plans skills, substitute these
paths wherever they reference `docs/superpowers/specs/` or `docs/superpowers/plans/`.

## Lifecycle: spec → issue → plan-comment → feature docs

These steps apply whether you use stock superpowers or the team fork:

1. **Spec → issue** (after the spec is approved): if the spec derives from an existing GitHub
   issue, append it as a comment (`gh issue comment <n> --body-file <spec>`). Otherwise ask
   `Create a GitHub tracking issue for this spec? (Y/n)` and on yes create it
   (`gh issue create --title "<slug>" --body-file <spec>`). Record `Tracking issue: <url>` in the
   spec file (a working copy — not committed). The issue is the spec's durable record.
2. **Plan → comment** (after the plan is saved): read the spec's `Tracking issue:` line and post
   the plan as a comment (`gh issue comment <n> --body-file <plan>`). Skip if no issue is linked.
3. **Implementation → docs** (after implementation completes): write a task-oriented
   usage/adaptation guide for the feature into `docs/<kebab-name>.md` — a how-to guide, not a
   dated changelog.

If `gh` is missing or unauthenticated, report and continue; never block on it.
