# The spec → issue → plan → docs lifecycle

The superpowers skills in this marketplace drive a fixed path for design work:
**brainstorm a spec, track it on GitHub, write a plan, ship feature docs.** Two
things are baked into the team's skills to make that happen automatically — a
hidden `.superpowers/` workspace for working docs, and a four-step lifecycle that
links each artifact to a GitHub issue. You don't run anything special; the skills
do it as you brainstorm and plan.

## How it works

The convention ships **two ways**, and both stay in sync:

- **Overlay (default):** stock `superpowers` + the `team-docs-convention` skill
  (`plugins/wp-labs-standards/skills/team-docs-convention/SKILL.md`). That skill is
  the single source of truth for the paths and the lifecycle prose; it loads
  whenever you brainstorm a spec or write a plan.
- **Fork (opt-in):** `wp-labs-superpowers`, a vendored fork of
  [`obra/superpowers`](https://github.com/obra/superpowers) with the paths and
  lifecycle baked directly into the skill text. Enable **either** stock superpowers
  **or** the fork — never both.

In the fork, the three lifecycle behaviors live as delimited **overlay fragments**
under `plugins/wp-labs-superpowers/team-overlays/` — one per skill
(`brainstorming.md`, `writing-plans.md`, `finishing-a-development-branch.md`). Each
fragment is wrapped in `<!-- wp-labs team overlay: BEGIN -->` / `<!-- ... END -->`
markers and is appended to the matching `skills/<name>/SKILL.md`.

The fork **auto-refreshes weekly** (`.github/workflows/refresh-superpowers-fork.yml`
→ `scripts/refresh-superpowers-fork.sh`): it re-copies the upstream skills, rewrites
the spec/plan paths to `.superpowers/...`, and **re-appends the overlay fragments**
(guarded by the BEGIN marker, so it never double-applies). That re-append step is
why a team behavior survives an upstream rebuild instead of being wiped.

## Using it

When you take a feature through brainstorming and planning, the skills do this for
you:

1. **Spec.** The approved design is written to the top-level repo's
   `.superpowers/01-specs/YYYY-MM-DD-HHmm-<name-of-spec>.md` (a working copy — not
   committed).
2. **Issue.** If the spec came from an existing GitHub issue, the spec is appended
   to it as a comment. Otherwise you're asked `Create a GitHub tracking issue for
   this spec? (Y/n)` and, on yes, `gh issue create` opens one. The resulting URL is
   recorded in the spec as a `Tracking issue:` line.
3. **Plan.** The implementation plan is written to the top-level repo's
   `.superpowers/02-plans/YYYY-MM-DD-HHmm-<name-of-plan>.md`, then posted as a
   comment on that tracking issue (`gh issue comment`).
4. **Feature docs.** When you finish the branch, you write a task-oriented guide
   (like this one) into `docs/` describing how to use and adapt the feature.

All `gh` steps degrade gracefully — if the GitHub CLI is missing or
unauthenticated, the step is skipped with a note and never blocks your work.

The entire `.superpowers/` tree is **git-ignored** by a committed
`.superpowers/.gitignore` (`*` plus `!.gitignore`, so the guard itself travels with
the repo on every branch and fresh clone). Specs and plans are local working copies;
the **GitHub tracking issue is their durable record**. Always use the **top-level
repository's** `.superpowers/` — when you're in a git worktree, resolve it to the
main working tree (`git -C "$(git rev-parse --git-common-dir)/.." rev-parse
--show-toplevel`) so all worktrees share one location and the docs outlive any single
worktree. Only the feature guide in `docs/` (step 4) is committed.

## When you might edit it

- **Change the paths or naming.** Edit the two path bullets and the lifecycle
  prose in `team-docs-convention/SKILL.md`, then update the `sed` replacement
  targets in `scripts/refresh-superpowers-fork.sh` so the next fork refresh emits
  the same paths. (The committed fork skills already use the new paths; the script
  keeps future refreshes aligned.)
- **Add or change a lifecycle behavior.** Edit the relevant fragment under
  `team-overlays/`, mirror the change in `team-docs-convention/SKILL.md` (so
  overlay users get it too), and append the fragment to the fork's `SKILL.md`.
  Because the refresh script re-appends from `team-overlays/`, the behavior
  persists across rebuilds — no other wiring needed.
- **Keep `FORK.md` honest.** The committed `plugins/wp-labs-superpowers/FORK.md`
  must byte-match the heredoc that `refresh-superpowers-fork.sh` regenerates;
  otherwise a refresh produces a spurious diff. Change both together.
- **Bump versions.** After editing a plugin, bump its `version` in
  `.claude-plugin/plugin.json` so teammates pick the change up on `/plugin update`.

To validate a change without waiting for the weekly job, run
`scripts/refresh-superpowers-fork.sh --check` (reports whether upstream is newer,
makes no changes) and `shellcheck scripts/refresh-superpowers-fork.sh`.
