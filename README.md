# claude-starter

A Claude Code **plugin marketplace** for the team. It packages our coding standards, common-task
helpers, and a curated plugin setup so everyone gets the same Claude Code experience from a single
`git` repo.

> Verified against Claude Code **2.1.179**.

## What's inside

This repo is itself the marketplace (`.claude-plugin/marketplace.json`). It ships three plugins:

| Plugin | What it gives you |
|---|---|
| **standards** | Coding-standard skills that auto-load by language: `general-coding-guidelines`, `python-style`, `typescript-style`, `css-style`, `sql-style`, plus `team-docs-convention` (our `docs/01-specs` + `docs/02-plans` paths). |
| **workflows** | `/commit` (our structured commit-message format) and the `git-pr-prepare` + `github-pr-review` skills. |
| **superpowers-team** | *Opt-in.* A fork of [superpowers](https://github.com/obra/superpowers) with our docs-path convention baked in. See [`plugins/superpowers-team/FORK.md`](plugins/superpowers-team/FORK.md). |

We also recommend a curated set of **external** plugins (see [Recommended setup](#recommended-setup)).

## Quick start (individual)

```text
/plugin marketplace add cssherry-wp/claude-starter
/plugin install standards@claude-starter
/plugin install workflows@claude-starter
```

Then enable the recommended external plugins:

```text
/plugin install code-review@claude-plugins-official
/plugin install code-simplifier@claude-plugins-official
/plugin install security-guidance@claude-plugins-official
/plugin install context7@claude-plugins-official
/plugin install playwright@claude-plugins-official
/plugin install typescript-lsp@claude-plugins-official
/plugin install superpowers@superpowers-marketplace
```

Browse or manage everything anytime with `/plugin`.

## Recommended setup

The default set (coding standards + workflows + stock superpowers + the curated externals) is in
[`team-settings.json`](team-settings.json). To adopt it for a project, merge that file's
`extraKnownMarketplaces` and `enabledPlugins` into the project's `.claude/settings.json` and commit
it — teammates get the marketplaces added and the plugins enabled automatically on clone (after the
workspace-trust prompt).

### Default-enabled

`standards`, `workflows`, `superpowers` (stock), `code-review`, `code-simplifier`,
`security-guidance`, `context7`, `playwright`, `typescript-lsp`.

### Opt-in (available, not enabled by default)

| Plugin | Add it when |
|---|---|
| `chrome-devtools-mcp@claude-plugins-official` | You need perf traces, Lighthouse, or memory profiling. Playwright already covers test writing + functional debugging, so add this only for perf/CWV/memory work. |
| `ralph-loop@claude-plugins-official` | You want the autonomous loop runner — better as an individual opt-in than a team default. |
| `superpowers-team@claude-starter` | You want our docs-path convention baked into superpowers itself. **Disable stock `superpowers` first** — never enable both (duplicate skill names). |

## Notes

### superpowers: overlay (default) vs fork (opt-in)

The docs-path convention ships two ways. **By default** we keep stock superpowers and rely on the
`team-docs-convention` skill (in `standards`) to redirect spec/plan output. The `superpowers-team`
fork is the alternative for teams that prefer the paths baked in. Run only one of them.

### If you already have personal copies of these skills

`workflows` provides `git-pr-prepare` and `github-pr-review`. If you also keep personal copies in
`~/.claude/skills/`, remove the personal copies to avoid duplicate skill names once the plugin is
enabled.

### Docs convention

Specs go to `docs/01-specs/YYYY-MM-DD-HHmm-<name>.md`; plans to
`docs/02-plans/YYYY-MM-DD-HHmm-<name>.md`.

## Maintaining

- Bump a plugin's `version` in its `.claude-plugin/plugin.json` when you change it; the team picks
  up changes on `/plugin update` (or `/plugin marketplace update claude-starter`).
- Refresh the superpowers fork per [`FORK.md`](plugins/superpowers-team/FORK.md) when upstream releases.
