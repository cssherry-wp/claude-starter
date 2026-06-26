# Spec: `.superpowers/` doc paths + spec→issue→comment→docs lifecycle

## Problem

Two things are wrong with how the team's superpowers setup handles specs and plans:

1. **Specs and plans land in a visible `docs/` subtree** (`docs/01-specs/`, `docs/02-plans/`).
   They are working artifacts, not shipped documentation, and clutter the docs folder. They
   should live in a hidden `.superpowers/` workspace folder instead.
2. **There is no link between a spec/plan and project tracking.** Specs are written and approved
   in isolation; nothing ties them to a GitHub issue, and the eventual feature ships with no
   user-facing documentation.

The convention ships **two ways** and both must stay in sync:

- **Overlay (default):** stock superpowers + the `team-docs-convention` skill in
  `wp-labs-standards`, which redirects spec/plan output.
- **Fork (opt-in):** `wp-labs-superpowers`, a vendored fork of `obra/superpowers` with the paths
  baked into the skill text. The fork **auto-rebuilds weekly** from upstream via
  `scripts/refresh-superpowers-fork.sh`, which wipes `skills/` and re-applies only path
  substitutions — so any new behavior baked into the fork must also be re-applied by that script
  or it disappears on the next refresh.

## Goals

1. Move spec/plan output to the hidden folder:
   - Specs → `.superpowers/01-specs/YYYY-MM-DD-HHmm-<name-of-spec>.md`
   - Plans → `.superpowers/02-plans/YYYY-MM-DD-HHmm-<name-of-plan>.md`
2. Add a tracking lifecycle, applied in **both** the overlay and the fork:
   - **Spec → issue:** after a spec is approved, append it to the existing GitHub issue it
     derives from, or (with confirmation) create a new tracking issue containing it.
   - **Plan → comment:** after the implementation plan is written, post it as a comment on that
     tracking issue.
   - **Implementation → docs:** after implementation is complete, review the repo `docs/` folder
     and write a lumen-style task-oriented usage/adaptation guide for the feature.
3. Ensure the fork's new behaviors **survive the weekly refresh**.

## Non-goals

- Changing the SDD scratch directory (`.superpowers/sdd/`) — it already uses `.superpowers/` and
  is out of scope.
- Changing upstream `obra/superpowers` itself.
- Migrating existing specs/plans already committed under `docs/01-specs` / `docs/02-plans`
  (leave history in place; the convention applies to new docs).

## Design

### 1. Path change

Replace `docs/01-specs` → `.superpowers/01-specs` and `docs/02-plans` → `.superpowers/02-plans`
everywhere they appear:

- `plugins/wp-labs-standards/skills/team-docs-convention/SKILL.md` (overlay source of truth)
- `plugins/wp-labs-superpowers/skills/brainstorming/SKILL.md`
- `plugins/wp-labs-superpowers/skills/brainstorming/spec-document-reviewer-prompt.md`
- `plugins/wp-labs-superpowers/skills/writing-plans/SKILL.md`
- `plugins/wp-labs-superpowers/skills/requesting-code-review/SKILL.md` (example text)
- `plugins/wp-labs-superpowers/skills/subagent-driven-development/SKILL.md` (example text)
- `plugins/wp-labs-superpowers/FORK.md`
- `README.md` ("Docs convention" section)
- `scripts/refresh-superpowers-fork.sh`: the `sed` substitution lines **and** the `FORK.md`
  heredoc it regenerates.

### 2. Lifecycle behaviors

The behaviors are triggered at three points. The **overlay** carries them as prose in the
`team-docs-convention` skill (which is already loaded "when brainstorming a spec, writing an
implementation plan, or referencing spec/plan files"). The **fork** bakes the same behavior into
its `brainstorming`, `writing-plans`, and `finishing-a-development-branch` skills at the matching
step.

#### 2a. Spec → issue (trigger: spec approved, in `brainstorming`)

After the user approves the written spec:

1. Determine the tracking issue. The spec derives from an existing issue if the conversation or
   spec references one (e.g. "issue #42", a GitHub issue URL). 
2. **If an existing issue is identified:** append the spec body as a comment
   (`gh issue comment <n> --body-file <spec>`).
3. **If none:** ask the user `Create a GitHub tracking issue for this spec? (Y/n)`. On yes (the
   default), `gh issue create` with the spec slug as title and the spec body as the issue body.
   On no, skip and note that no issue is linked.
4. Record the resulting issue reference in the spec file as a `Tracking issue: <url>` line
   (in the spec's metadata block) so later steps can find it without re-asking.

Guard: if `gh` is unavailable or unauthenticated, report it and continue (don't block the spec).

#### 2b. Plan → comment (trigger: plan written/saved, in `writing-plans`)

After the plan file is saved:

1. Read the `Tracking issue:` reference from the spec the plan is based on.
2. If present, post the plan as a comment (`gh issue comment <n> --body-file <plan>`).
3. If absent (no linked issue), skip with a one-line note.

#### 2c. Implementation → docs (trigger: implementation complete, in `finishing-a-development-branch`)

As a step in the finishing flow (after tests pass, before/at the integration options):

1. Review the existing `docs/` folder to match its structure and style.
2. Write a **task-oriented usage/adaptation guide** for the feature in lumen style: a `# Title`,
   a one-line **Goal**, then numbered sections with concrete steps, commands, and references to
   real files in the repo (e.g. `app/helpers/edwh.py`). This is a how-to guide, **not** a dated
   changelog. Save it to `docs/<kebab-feature-name>.md`.
3. The guide explains how a teammate would *use* the feature and how they would *adapt/extend*
   it.

### 3. Refresh survival

Store each fork behavior as a delimited **team-overlay fragment** under
`plugins/wp-labs-superpowers/team-overlays/`:

- `brainstorming.md` — the spec→issue section
- `writing-plans.md` — the plan→comment section
- `finishing-a-development-branch.md` — the feature-docs section

Each fragment is wrapped in a marker:

```
<!-- wp-labs team overlay: BEGIN -->
... behavior prose ...
<!-- wp-labs team overlay: END -->
```

`scripts/refresh-superpowers-fork.sh` gains two changes:

1. The existing path `sed` lines change target to `.superpowers/01-specs` / `.superpowers/02-plans`.
2. A new **append step** (run after the upstream copy + path substitution): for each fragment,
   if its target `SKILL.md` does not already contain the BEGIN marker, append the fragment.
   Idempotent — re-running never double-appends.

The committed fork skills get the fragments applied **now** (append once), so the behavior is live
immediately without waiting for a refresh.

## Components / files touched

| File | Change |
|---|---|
| `team-docs-convention/SKILL.md` | paths → `.superpowers/...`; add lifecycle prose |
| fork `brainstorming/SKILL.md` + `spec-document-reviewer-prompt.md` | paths; append spec→issue overlay |
| fork `writing-plans/SKILL.md` | paths; append plan→comment overlay |
| fork `finishing-a-development-branch/SKILL.md` | append feature-docs overlay |
| fork `requesting-code-review/SKILL.md`, `subagent-driven-development/SKILL.md` | example paths |
| `plugins/wp-labs-superpowers/team-overlays/*.md` | **new** fragment files |
| `scripts/refresh-superpowers-fork.sh` | sed targets + append step |
| `FORK.md`, `README.md` | doc references |
| `plugins/wp-labs-superpowers/.claude-plugin/plugin.json` | version bump (`-team.N`) |
| `plugins/wp-labs-standards/.claude-plugin/plugin.json` | version bump |

## Error handling / edge cases

- `gh` missing or unauthenticated → report, skip the issue/comment step, never block the workflow.
- No linked issue and user declines creation → spec records "no tracking issue"; plan step skips.
- Refresh re-run when overlay already applied → BEGIN-marker check makes it a no-op.
- Spec/plan filenames keep the 24-hour `HHmm` timestamp so same-day docs sort correctly.

## Testing / verification

- `shellcheck scripts/refresh-superpowers-fork.sh` passes.
- Dry-run the append logic on a scratch copy: appending twice yields one overlay block.
- Grep confirms no remaining `docs/01-specs` / `docs/02-plans` references outside historical
  committed specs/plans.
- Manual read-through of each edited skill for internal consistency.

## Tracking issue

https://github.com/cssherry-wp/wp-labs-starter/issues/13
