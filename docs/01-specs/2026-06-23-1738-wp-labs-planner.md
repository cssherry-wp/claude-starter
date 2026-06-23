# wp-labs-planner — Daily & Weekly Obsidian Planner

**Status:** Draft for review
**Date:** 2026-06-23
**Author:** Sherry Zhou

## 1. Summary

A personal planner distributed as a Claude Code plugin (`wp-labs-planner`) in the
`wp-labs-starter` marketplace. The plugin bundles a Python tool that generates two
Obsidian notes:

- A **daily note** aggregating, from multiple sources, what was accomplished so far
  this week, learnings and follow-ups from OneNote, todos from a Google Doc, and a
  summary of upcoming calls.
- A **weekly overview** that updates the status of every in-progress project and
  produces a todo list grouped by project, with urgent items pinned to the top of
  each group.

Collectors gather raw text mechanically; headless Claude Code (`claude -p`) does the
summarizing, classifying, grouping, and priority assignment. Output is
Obsidian-flavored Markdown written into the user's vault.

The plugin's `planner-setup` skill is the user-facing entry point: it checks whether
the planner is already installed/configured/scheduled and, if not, walks the user
through bootstrapping it.

## 2. Goals & non-goals

**Goals**
- One-command setup via the plugin skill, with a status check that is safe to re-run.
- Daily and weekly notes that drop cleanly into an existing Obsidian + Templater +
  Dataview + Tasks workflow and respect its conventions.
- Resilience: a failing data source degrades to a placeholder, never aborts the run.
- Self-contained and runnable unattended (manual now, scheduler-ready).

**Non-goals**
- No calendar API: calls arrive as emails to the `+planner` alias.
- No Microsoft Graph / OneNote API: notebooks are local `.one` files.
- The planner never *creates* project notes or daily templates (the user's own
  Templater templates own creation); it only reads and appends.
- No separate Claude API key — summarization runs through `claude -p`.

## 3. Inputs

| Source | Access | Used for |
| --- | --- | --- |
| Gmail (`<user>+planner@<domain>`) | Gmail API, read-only | (a) accomplishment notes for the week; (b) upcoming-call detection from invite emails |
| Google Doc | Google Docs API, read-only (same OAuth as Gmail) | rolling todos |
| OneNote `.one` files | local files → pluggable converter command | learnings + follow-up actions |
| Obsidian vault | local Markdown | rolling personal todos, follow-ups, project notes, generated output |

Auth: a single Google OAuth desktop-app credential covers Gmail (read-only) and Docs
(read-only). First run opens a browser consent flow; the token is cached to a
gitignored `token.json`. `credentials.json` is created by the user in a Google Cloud
project (README walkthrough).

## 4. Vault conventions (source of truth)

The tool conforms to the user's existing vault setup; it does not impose new ones.

- **Daily template** (Templater): frontmatter `tags: [YYYY/MM/DD, Daily]`,
  yesterday/tomorrow nav links, `## Notes`, then Dataview blocks `## TODO`
  (priority-sorted), `### Completed / Cancelled`, `### References`. The TODO Dataview
  sorts by Tasks-plugin priority emojis: 🔺 (0) ⏫ (1) 🔼 (2) 🔽 (3) ⏬ (4), default 2.5.
- **Projects** live under `00-InProgress/<Name>/00-<Name>.md`, tagged
  `#project/<Name>`, with sections `## Summary`, `## Members`, `## Timeline`,
  Dataview `## TODO` / `### Completed` / `### Cancelled`, and `## References`.
  Project tasks are matched by Dataview where a heading subpath contains the project
  name. A `## Status` section is maintained by the weekly script (see §6).
- **Members** are people-tags of the form `#<company>/<first_last>`, where company is
  `#wp` (Warburg), `#contractor`, or an actual company name (e.g. `#wp/jane_doe`,
  `#contractor/john_smith`). Synthesis uses these tags when referring to people.
- **`zz-Templates`** is excluded from all task/reference scans, matching the vault's
  Dataview `FROM -"zz-Templates"` convention.

## 5. Architecture

A new plugin modeled on `wp-labs-sdlc`:

```
plugins/wp-labs-planner/
  .claude-plugin/plugin.json
  skills/planner-setup/
    SKILL.md                       # check-status-then-bootstrap entry point
    scripts/                       # the bundled Python tool (installed on setup)
      pyproject.toml               # deps: google-api-python-client, google-auth-oauthlib, pyyaml
      planner/
        config.py                  # load + validate config.yaml
        collectors/
          gmail.py                 # accomplishment notes + upcoming calls
          gdoc.py                  # todos from the Google Doc
          onenote.py               # .one -> markdown via pluggable converter
          vault.py                 # read projects, open tasks, state files
        synthesis.py               # wraps `claude -p` calls + prompt assembly
        render_daily.py            # port of the Templater daily template + injected sections
        render_weekly.py           # weekly overview + project ## Status / timeline updates
        daily.py                   # entry point:  python -m planner.daily
        weekly.py                  # entry point:  python -m planner.weekly
      tests/                       # pytest mirroring module structure
    templates/
      Daily.md                     # the user's Templater daily template (installed into vault)
      config.example.yaml
      prompts/{daily,weekly}_synthesis.md
      launchd/                     # macOS plist examples (daily + Friday weekly)
```

Each collector is independently testable and returns **raw Markdown text**. The two
entry scripts are thin: gather → synthesize → render. Synthesis is the only component
that shells out to `claude`.

### 5.1 `planner-setup` skill

When invoked, it **checks status** and reports each item, then bootstraps anything
missing:

1. Python tool installed to the user-chosen working directory, deps present.
2. `config.yaml` present and valid.
3. Google OAuth: `credentials.json` present, `token.json` cached (runs the consent
   flow if not).
4. OneNote converter installed and on PATH.
5. `Daily.md` template copied into the vault's templates folder.
6. Schedule: launchd jobs installed (optional) — daily, plus weekly on Fridays.
7. A recent daily note exists (sanity signal that runs are happening).

The check is idempotent and safe to re-run; "is it running?" = items 1–6 satisfied and
a recent daily note present.

## 6. Behavior

### Daily (`python -m planner.daily`)
1. Read vault open tasks and state files.
2. Gmail: accomplishments = messages to `<user>+planner@<domain>` since the start of
   the current ISO week, excluding invites; upcoming calls = messages carrying
   calendar invites (`.ics`) or detected as meeting invites, future-dated.
3. Google Doc: fetch by ID → todo text.
4. OneNote: convert each configured `.one` file → Markdown.
5. Synthesis (`prompts/daily_synthesis.md`): produce the injected sections and assign a
   priority emoji to each new task.
6. Render: the daily note is generated **outside** Obsidian, so `render_daily.py` ports
   the Templater template's resolved logic — it computes the `YYYY/MM/DD` tag and
   yesterday/tomorrow links from the note's date and emits the three Dataview blocks
   **verbatim** (they render live in Obsidian). Under `## Notes` it injects:
   - `### 📅 Upcoming Calls`
   - `### ✅ This Week So Far`
   - `### 📓 Learnings & Follow-ups`
   - new **tasks** from the Google Doc and OneNote follow-ups, as checkboxes with
     priority emojis.

   The user's rolling personal todos and follow-ups already live in the vault as tasks,
   so the template's `## TODO` Dataview surfaces them urgent-first automatically; the
   script only adds *new* items. Output file: `<daily_dir>/YYYY-MM-DD.md`.

### Weekly (`python -m planner.weekly`) — run on the Friday before the week
1. Enumerate `00-InProgress/<Name>/00-<Name>.md`; gather the week's sources and all
   open vault tasks (excluding `zz-Templates`) with note/heading context.
2. Synthesis (`prompts/weekly_synthesis.md`):
   - a one-line dated **status** per project (progress this week + what's next);
   - a todo list **grouped by project** (via the project list + `#project/<Name>`
     tags) with urgent items (🔺⏫) pinned to the top of each group.
3. Render:
   - Write `<weekly_dir>/YYYY-MM-DD-week-overview.md` (date = generation/Friday day),
     frontmatter tagged `Weekly`, each group headed by a `[[00-<Name>|<Name>]]` link.
   - For each project, update its `## Status` section in place: insert the dated status
     line newest-first, preserving prior entries; create the section if absent. Back up
     the project file before writing.

## 7. Config (`config.yaml` — paths/IDs only, no secrets)

- `google`: `credentials_path`, `token_path`, `planner_address`, `gdoc_id`
- `onenote`: list of `.one` paths, `converter_command`
- `vault`: vault path, `templates_dir`, `projects_dir` (`00-InProgress`),
  `daily_output_dir`, `weekly_output_dir`, optional rolling todo/follow-up file paths
- `claude`: command (default `claude`) and any flags

## 8. OneNote conversion risk

Raw `.one` is undocumented binary — the single fragile piece. Conversion is a
**pluggable command** (`converter_command`) so the tool can be swapped without code
changes. The best-maintained `.one`→Markdown/HTML converter will be selected and its
install steps documented during planning. If conversion fails at runtime, the collector
logs a warning and the note shows a `⚠️ OneNote unavailable` placeholder.

## 9. Error handling

- Collectors are isolated: a failing/empty source degrades to a placeholder section;
  the run still produces a note.
- If `claude -p` synthesis fails, the raw collected material is written under a banner
  so nothing is lost.
- Config is validated up front with actionable messages; auth failures print re-auth
  instructions.
- Vault writes (project `## Status`) back up the target file first.

## 10. Testing

Pytest mirroring module structure, with fixtures: sample Gmail API JSON, a
pre-converted OneNote fixture, sample Google Doc text, sample vault project notes and
task files. External APIs and the `claude` subprocess are mocked. Coverage includes the
happy path, a failing/empty source per collector, daily render correctness (resolved
tags, nav links, verbatim Dataview blocks, injected sections, priority emojis), and
weekly correctness (grouped-todo ordering, dated `## Status` insertion, backup).

## 11. README / setup walkthrough

Bundled with the plugin and surfaced by `planner-setup`: Python/venv/deps → Google
Cloud OAuth client (Gmail + Docs scopes) → OneNote converter install → `config.yaml` →
vault paths and template install → running each script manually → optional macOS
`launchd` schedule (daily + Friday weekly).

## 12. Open items for planning

- Selection and install steps for the OneNote `.one` converter.
- Exact Gmail query/heuristics distinguishing accomplishment emails from invite emails.
- Whether `launchd` install is offered interactively by `planner-setup` or documented
  only.
