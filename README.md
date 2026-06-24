# wp-labs-starter

A Claude Code **plugin marketplace** for the team. It packages our coding standards, common-task
helpers, and a curated plugin setup so everyone gets the same Claude Code experience from a single
`git` repo.

> Verified against Claude Code **2.1.179**.

## What's inside

This repo is itself the marketplace (`.claude-plugin/marketplace.json`). It ships three plugins:

| Plugin | What it gives you |
|---|---|
| **wp-labs-standards** | Coding-standard skills (`general-coding-guidelines`, `python-style`, `typescript-style`, `css-style`, `sql-style`, `team-docs-convention`) **plus** the common-task workflows `/commit` (structured commit-message format), `change-review` (broad review dispatcher — see [review-skills map](plugins/wp-labs-standards/skills/change-review/review-skills-map.md)), `github-pr-prepare`, and `github-pr-review`. A `PreToolUse` hook also injects the matching standard **deterministically by file type** on every edit (see [Deterministic standards](#deterministic-standards)). |
| **wp-labs-sdlc** | The `scaffolding-sdlc` skill: interactively bootstraps a repo's SDLC — a runnable starter app (TypeScript / Python+Django / fullstack Python+React), a Makefile task runner, a git pre-commit hook, GitHub Actions for lint/typecheck/unit/Playwright-e2e/security gates, Dependabot, PR-status labels, PR auto-rebase, the Claude review/triage workflows, and an optional hosting layer (Docker + docker-compose + Azure Bicep deploy). On an existing repo it audits what's present and adds only the missing pieces. |
| **wp-labs-superpowers** | *Opt-in.* A fork of [superpowers](https://github.com/obra/superpowers) with our docs-path convention baked in. See [`plugins/wp-labs-superpowers/FORK.md`](plugins/wp-labs-superpowers/FORK.md). |

We also recommend a curated set of **external** plugins (see [Recommended setup](#recommended-setup)).

## Quick start (individual)

```text
/plugin marketplace add cssherry-wp/wp-labs-starter
/plugin install wp-labs-standards@wp-labs-starter
/plugin install wp-labs-sdlc@wp-labs-starter
```

Then enable the recommended external plugins:

```text
/plugin install code-review@claude-plugins-official
/plugin install code-simplifier@claude-plugins-official
/plugin install security-guidance@claude-plugins-official
/plugin install context7@claude-plugins-official
/plugin install playwright@claude-plugins-official
/plugin install typescript-lsp@claude-plugins-official
/plugin install superpowers@claude-plugins-official
```

Browse or manage everything anytime with `/plugin`.

## Recommended setup

The default set (wp-labs-standards + stock superpowers + the curated externals) is in
[`team-settings.json`](team-settings.json). To adopt it for a project, merge that file's
`extraKnownMarketplaces` and `enabledPlugins` into the project's `.claude/settings.json` and commit
it — teammates get the marketplaces added and the plugins enabled automatically on clone (after the
workspace-trust prompt).

### Default-enabled

`wp-labs-standards`, `superpowers` (stock), `code-review`, `code-simplifier`,
`security-guidance`, `context7`, `playwright`, `typescript-lsp`.

`wp-labs-sdlc` is available but not default-enabled — install it when you need to scaffold or top up
a repo's SDLC automation.

### Opt-in (available, not enabled by default)

| Plugin | Add it when |
|---|---|
| `wp-labs-sdlc@wp-labs-starter` | You're starting a repo or adding CI/test/security/hosting automation to one. |
| `chrome-devtools-mcp@claude-plugins-official` | You need perf traces, Lighthouse, or memory profiling. Playwright already covers test writing + functional debugging, so add this only for perf/CWV/memory work. |
| `ralph-loop@claude-plugins-official` | You want the autonomous loop runner — better as an individual opt-in than a team default. |
| `wp-labs-superpowers@wp-labs-starter` | You want our docs-path convention baked into superpowers itself. **Disable stock `superpowers` first** — never enable both (duplicate skill names). |

## Notes

### Deterministic standards

Skills are model-invoked from their `description`, so language standards only *usually* load.
To make them fire reliably, the `wp-labs-standards` plugin ships a `PreToolUse` hook
(`hooks/inject-standards.js`) on `Edit|Write|MultiEdit`: it reads the target file's extension
and injects the matching standard on **every** edit — no model judgment involved.

- `.py` → `python-style`
- `.ts/.tsx/.js/.jsx/.mjs/.cjs` → `typescript-style`
- `.css/.scss/.sass` → `css-style`

The hook reads the same `SKILL.md` files (single source of truth — no duplicated content). The
skills also stay model-invocable, which covers reviewing/discussing these files when no edit
happens (the hook only fires on edits).

**SQL is deliberately excluded** from the hook: the `.sql` extension is an unreliable signal
(SQL is often embedded in `.py`/`.ts` and migration files), so `sql-style` remains a normal
model-invoked skill. `general-coding-guidelines` and `team-docs-convention` are likewise
skill-only (not file-type specific).

The hook runs on `node` (always present wherever Claude Code runs), so there's no extra
dependency to install.

### superpowers: overlay (default) vs fork (opt-in)

The docs-path convention ships two ways. **By default** we keep stock superpowers and rely on the
`team-docs-convention` skill (in `wp-labs-standards`) to redirect spec/plan output. The
`wp-labs-superpowers` fork is the alternative for teams that prefer the paths baked in. Run only one
of them.

### If you already have personal copies of these skills

`wp-labs-standards` provides `github-pr-prepare` and `github-pr-review`. If you also keep personal
copies in `~/.claude/skills/`, remove the personal copies to avoid duplicate skill names once the
plugin is enabled.

### Docs convention

Specs go to `docs/01-specs/YYYY-MM-DD-HHmm-<name>.md`; plans to
`docs/02-plans/YYYY-MM-DD-HHmm-<name>.md`.

## Maintaining

- Bump a plugin's `version` in its `.claude-plugin/plugin.json` when you change it; the team picks
  up changes on `/plugin update` (or `/plugin marketplace update wp-labs-starter`).
- The superpowers fork refreshes itself: a weekly GitHub Actions workflow
  ([`.github/workflows/refresh-superpowers-fork.yml`](.github/workflows/refresh-superpowers-fork.yml))
  tracks the superpowers snapshot pinned by `anthropics/claude-plugins-official` and opens a PR when
  a new version appears. Run it on demand from the Actions tab, or locally via
  `scripts/refresh-superpowers-fork.sh` (see [`FORK.md`](plugins/wp-labs-superpowers/FORK.md)).
