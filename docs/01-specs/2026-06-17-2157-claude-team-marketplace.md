# Spec: claude-starter — Claude Code Team Marketplace

**Date:** 2026-06-17
**Status:** Approved (design), pending implementation
**Target Claude Code version:** 2.1.179 (verified locally; manifest schema cross-checked against official docs)
**Repo:** https://github.com/cssherry-wp/claude-starter

## Goal

Package one engineer's personal Claude Code preferences, common tasks, and
frequently-used plugins into a **git-hosted plugin marketplace** the whole team
can install with `/plugin marketplace add cssherry-wp/claude-starter`. The repo
itself is the marketplace; everything ships from this single repo.

## Scope decisions (from brainstorming)

- **Distribution:** git repo → GitHub (`cssherry-wp/claude-starter`).
- **Coding standards:** shipped as auto-triggering skills (one per language + one general), not committed CLAUDE.md.
- **Common tasks:** `/commit` command, plus migrated `git-pr-prepare` and `github-pr-review` skills.
- **Reload:** updated rules picked up in-session; no reload command shipped (`/reload-plugins` is built-in).
- **Superpowers customization:** both options ship, but the **overlay skill is the default**;
  the vendored fork is available as an opt-in alternative.
- **Naming:** neutral `standards` / `workflows` plugin names.

### Superpowers customization — finding

Diffing the installed superpowers against pristine upstream:
- Official 6.0.2 install is **identical** to upstream.
- obra 5.1.0 install differs from pristine v5.1.0 in exactly one *intentional* way: a
  **docs-directory convention** applied across 5 skill files:
  - specs → `docs/01-specs/YYYY-MM-DD-HHmm-<name>.md`
  - plans → `docs/02-plans/YYYY-MM-DD-HHmm-<name>.md`
- `AGENTS.md`/`CLAUDE.md` deltas are obra's contributor-policy text (commit-vs-tag drift), **excluded**.

The change is a path convention (not forked skill logic). Two delivery options ship:
1. **Overlay skill — DEFAULT** (`team-docs-convention` in the `standards` plugin): states the
   convention; steers all spec/plan work (including stock superpowers) via instruction
   precedence. Zero maintenance, and enabled by default in `team-settings.json`.
2. **Vendored fork — opt-in** (`superpowers-team` plugin): a copy of upstream superpowers
   **6.0.2** with the path replacements applied in-tree, for teams that want the behavior
   baked in rather than relying on instruction precedence. Present in the marketplace but
   **not** enabled by default.

## Repository layout

```
claude-starter/                         # the marketplace repo (= this repo)
├── .claude-plugin/
│   └── marketplace.json                # catalog: name "claude-starter", lists 3 plugins
├── plugins/
│   ├── standards/
│   │   ├── .claude-plugin/plugin.json
│   │   └── skills/
│   │       ├── general-coding-guidelines/SKILL.md
│   │       ├── python-style/SKILL.md
│   │       ├── typescript-style/SKILL.md
│   │       ├── css-style/SKILL.md
│   │       ├── sql-style/SKILL.md
│   │       └── team-docs-convention/SKILL.md
│   ├── workflows/
│   │   ├── .claude-plugin/plugin.json
│   │   ├── commands/commit.md
│   │   └── skills/
│   │       ├── git-pr-prepare/SKILL.md
│   │       └── github-pr-review/
│   │           ├── SKILL.md
│   │           └── evaluations/*.json
│   └── superpowers-team/               # vendored fork (opt-in) of upstream superpowers 6.0.2
│       ├── .claude-plugin/plugin.json  # name superpowers-team, records upstream base sha
│       ├── FORK.md                     # what diverges + how to refresh
│       └── skills/...                  # full superpowers skill tree, doc paths rewritten
├── team-settings.json                  # template the team merges into .claude/settings.json
├── docs/01-specs/2026-06-17-2157-claude-team-marketplace.md   # this spec
└── README.md                           # install + usage instructions
```

## Component detail

### Plugin: standards

Six skills. Each `SKILL.md` carries a `description:` that makes Claude auto-load it when the
relevant work appears. Content migrated verbatim from `~/.claude/rules/*.md` (general from
`coding-guidelines.md`, now `alwaysApply: true`).

| Skill | description trigger |
|---|---|
| `general-coding-guidelines` | any time writing, reviewing, or refactoring code |
| `python-style` | editing/creating Python (`.py`) |
| `typescript-style` | editing/creating JS/TS/React (`.ts/.tsx/.js/.jsx`) |
| `css-style` | editing/creating CSS/Sass |
| `sql-style` | writing SQL, schema, or migrations |
| `team-docs-convention` | brainstorming specs or writing plans — pins `docs/01-specs/` and `docs/02-plans/` with `YYYY-MM-DD-HHmm` naming (DEFAULT superpowers customization) |

Note: skills auto-load by description match; truly always-on enforcement is a property of
committed CLAUDE.md. Per the brainstorming choice we use skills for cross-repo portability.

### Plugin: workflows

- **`/commit`** (`commands/commit.md`): generates a commit following the mandated body
  format — subject (≤50 chars), `Logic:`, `Alternatives considered:`, `Caveats/assumptions:`.
  Omits a section only when genuinely inapplicable.
- **`git-pr-prepare`** and **`github-pr-review`**: copied verbatim from `~/.claude/skills/`,
  including the latter's `evaluations/` fixtures.

### Plugin: superpowers-team (vendored fork, opt-in)

- Base: upstream superpowers **6.0.2** (obra/superpowers, sha `b62616f`), copied into the repo.
- Single edit applied across the tree: `docs/superpowers/specs` → `docs/01-specs` and
  `docs/superpowers/plans` → `docs/02-plans`, adopting `YYYY-MM-DD-HHmm-<name>` naming in the
  affected skill/reviewer-prompt text.
- `plugin.json` records the upstream base sha; `FORK.md` documents divergence + refresh steps.
- Not enabled by default. README explains the trade-off and how to switch.

### team-settings.json (distribution template — overlay default)

```json
{
  "extraKnownMarketplaces": {
    "claude-starter": { "source": { "source": "github", "repo": "cssherry-wp/claude-starter" } },
    "superpowers-marketplace": { "source": { "source": "github", "repo": "obra/superpowers-marketplace" } }
  },
  "enabledPlugins": {
    "standards@claude-starter": true,
    "workflows@claude-starter": true,
    "superpowers@superpowers-marketplace": true,
    "code-review@claude-plugins-official": true,
    "code-simplifier@claude-plugins-official": true,
    "security-guidance@claude-plugins-official": true,
    "context7@claude-plugins-official": true,
    "playwright@claude-plugins-official": true,
    "typescript-lsp@claude-plugins-official": true
  }
}
```

Default = stock superpowers + the `team-docs-convention` overlay (from `standards`). To use the
fork instead, the team disables `superpowers@superpowers-marketplace` and enables
`superpowers-team@claude-starter` (never both — duplicate skill names).

**Opt-in plugins** (documented in the README, not in the default `enabledPlugins`): the team
adds these when needed —
- `chrome-devtools-mcp@claude-plugins-official` — perf traces, Lighthouse, memory profiling
  (Playwright covers test writing + functional debugging; add this only for perf/CWV/memory work).
- `ralph-loop@claude-plugins-official` — autonomous loop runner; better as an individual opt-in.
- `superpowers-team@claude-starter` — the vendored fork (see above).

## Manifests

- `marketplace.json`: `name: claude-starter`, `owner`, `plugins[]` with `source: ./plugins/<name>`.
- Each `plugin.json`: `name`, `version: 0.1.0` (fork carries its upstream-derived version + base sha),
  `description`, `author`. Explicit semver so the team updates only on a deliberate bump.

## Out of scope / caveats

- Coding-standard skills rely on description-match auto-loading, not guaranteed always-on.
- The opt-in fork and stock superpowers must not be enabled together (duplicate skill names);
  README states this.
- The vendored fork must be manually refreshed on upstream superpowers releases; recorded base
  sha + `FORK.md` make this a copy + re-apply of the path replacements.
- Default external set (code-review, code-simplifier, security-guidance, context7, playwright,
  typescript-lsp) is a starting point; chrome-devtools-mcp, ralph-loop, and the superpowers fork
  are opt-in. The team can add/remove entries in `team-settings.json`.
- Verification is `claude plugin validate` on each manifest (no runtime tests apply to static config).
