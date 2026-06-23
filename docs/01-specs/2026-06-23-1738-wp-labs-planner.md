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

Collectors gather raw text mechanically; a configurable LLM backend — headless Claude
Code (`claude -p`) by default, or a local model (e.g. Ollama) — does the summarizing,
classifying, grouping, and priority assignment. Output is Obsidian-flavored Markdown
written into the user's vault.

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
- No calendar API: calendar and email summaries arrive as emails to the `+planner` alias.
- No Microsoft Graph / OneNote API: notebooks are local `.one` files.
- The planner *creates* the daily and weekly Templater templates — installing the
  provided daily template and authoring a matching weekly template — but never creates
  project notes. Project notes are only appended to / modified.
- No separate Claude API key — summarization runs through a configurable LLM backend:
  headless `claude -p` by default, or a **local model** (e.g. Ollama) for fully offline
  runs. The backend is pluggable; collectors and rendering are backend-agnostic.

## 3. Inputs

| Source | Access | Used for |
| --- | --- | --- |
| Gmail (`<user>+planner@<domain>`) | Gmail API, read-only | (a) accomplishment notes for the week; (b) upcoming-call detection from invite emails |
| Google Doc | Google Docs API, read-only (same OAuth as Gmail) | rolling todos |
| OneNote `.one` files | local files → pluggable converter command | learnings + follow-up actions |
| Obsidian vault | local Markdown (+ git history if the vault is a repo) | rolling personal todos, follow-ups, project notes, recently-touched notes for context, generated output |

Auth: a single Google OAuth desktop-app credential covers Gmail (read-only) and Docs
(read-only). First run opens a browser consent flow; the token is cached to a
gitignored `token.json`. `credentials.json` is created by the user in a Google Cloud
project (README walkthrough).

## 4. Vault conventions (source of truth)

The tool conforms to the user's existing vault setup; it does not impose new ones.

- **Daily template** (Templater, provided by the user, installed by the planner):
  frontmatter `tags: [YYYY/MM/DD, Daily]`, yesterday/tomorrow nav links, `## Notes`,
  then Dataview blocks `## TODO` (priority-sorted), `### Completed / Cancelled`,
  `### References`. The TODO Dataview sorts by Tasks-plugin priority emojis:
  🔺 (0) ⏫ (1) 🔼 (2) 🔽 (3) ⏬ (4), default 2.5.
- **Weekly template** (Templater, authored by the planner in the daily template's
  style, installed into the vault): frontmatter `tags: [Weekly]`, then a Dataview
  `TASK` block that groups open vault tasks by `#project/<Name>` with the same
  priority-emoji sort (urgent-on-top per group). The planner appends a static
  synthesized snapshot underneath the Dataview when it generates each weekly note
  (see §6).
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
  .mcp.json                        # native obsidian /mcp/ (http) via Bearer ${OBSIDIAN_API_KEY} (§5.2)
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
          vault.py                 # projects, open tasks, state files, recent notes (mtime + git)
        obsidian.py                # integration layer: MCP/Local REST API | obsidian:// URI (§5.2)
        synthesis.py               # prompt assembly + pluggable LLM backend (claude -p | local model)
        render_daily.py            # expand Obsidian Daily template (obsidian:// URI) + injected sections
        render_weekly.py           # weekly note (Dataview + static snapshot) + project ## Status updates
        daily.py                   # entry point:  python -m planner.daily
        weekly.py                  # entry point:  python -m planner.weekly
      tests/                       # pytest mirroring module structure
    templates/
      Daily.md                     # provided daily Templater template (installed into vault)
      Weekly.md                    # weekly Templater template authored from Daily.md (installed into vault)
      config.example.yaml
      prompts/{daily,weekly}_synthesis.md
      launchd/                     # macOS plist examples (daily + Friday weekly)
```

Each collector is independently testable and returns **raw Markdown text**. The two
entry scripts are thin: gather → synthesize → render. Synthesis is the only component
that calls the LLM backend (shells out to `claude -p` or a local model).

### 5.1 `planner-setup` skill

When invoked, it **checks status** and reports each item, then bootstraps anything
missing:

1. Python tool installed to the user-chosen working directory, deps present.
2. `config.yaml` present and valid.
3. Google OAuth: `credentials.json` present, `token.json` cached (runs the consent
   flow if not).
4. OneNote converter installed and on PATH.
5. LLM backend reachable: `claude` on PATH, or (for `local`) the model server/command
   responds.
6. `Daily.md` and `Weekly.md` templates copied into the vault's templates folder.
7. Schedule: launchd jobs installed (optional) — daily, plus weekly on Fridays.
8. A recent daily note exists (sanity signal that runs are happening).

The check is idempotent and safe to re-run; "is it running?" = items 1–7 satisfied and
a recent daily note present.

### 5.2 Obsidian integration layer

A thin `obsidian.py` abstracts how the tool talks to the vault. The chosen stack is the
[`obsidian-local-rest-api`](https://github.com/coddingtonbear/obsidian-local-rest-api)
plugin (v4.1.3, "Local REST API with MCP"), using its **built-in MCP server** at
`POST https://127.0.0.1:27124/mcp/` (Streamable HTTP transport, API key as bearer token).
This replaces the third-party `mcp-obsidian` (stdio) — see "Why the native server" below.

- **Native MCP tools (note I/O).** `vault_list`, `vault_read` (content + frontmatter +
  tags + **stat/mtime**), `vault_write`, `vault_append`, `vault_patch` (heading / block /
  frontmatter — used to inject under `## Notes` and to update project
  `## Status`/`## Timeline`), `vault_delete`, `vault_move`, `vault_get_document_map`,
  `periodic_note_get_path`, `search_query` (JsonLogic), `search_simple`, `tag_list`,
  `command_list`, `command_execute`, `open_file`, `active_file_get_path`.
- **Why the native server (resolves the version mismatch).** The third-party
  `mcp-obsidian` v1.28.0 targets endpoints this plugin version doesn't expose:
  `get_recent_changes` POSTs `/search/` with `application/vnd.olrapi.dataview.dql+txt`,
  which v4.1.3 rejects (err 40012 — it only accepts `…jsonlogic+json`), and
  `get_recent_periodic_notes` hits `/periodic/{period}/recent`, which doesn't exist
  (err 40054). The plugin's own MCP server can't drift from the plugin, and its richer
  toolset covers the gaps: **recent-change discovery** uses `vault_read` stat or
  `search_query`; **periodic notes** use `periodic_note_get_path`.
- **Verified live (2026-06-23).** Native `/mcp/` handshake returns a session
  (`serverInfo: obsidian-local-rest-api`, protocol `2025-06-18`) and `tools/list` returns
  all 16 tools. `00-InProgress` lists the real projects (A5, Duravant, Esentire, Hexarmor,
  Infinite, Qualifacts, SDLC, VIP, WarburgTA, iNRCORE); `zz-Templates/Daily.md` reads
  back; daily notes live in `zz-Sherry_Daily/YYYY-MM-DD.md` and `## Notes` is already
  authored as `### <topic> #project/<Name>` blocks (matching §6). A heading-relative
  patch under `## Notes` succeeded and was restored byte-for-byte — the planner's core
  write op.
- **Periodic-note tool, tested (2026-06-23).** `periodic_note_get_path(daily)` returns
  `zz-Sherry_Daily/2026-06-23.md` (daily notes enabled) — the planner uses it to locate
  today's note. `periodic_note_get_path(weekly)` errors *"Specified period is not
  enabled"* (weekly notes off in Periodic Notes), so the weekly note must NOT depend on
  it — the planner writes `weekly_output_dir/YYYY-MM-DD-week-overview.md` directly. There
  is **no native "list recent periodic notes" tool**, so "last week's notes" discovery
  lists `zz-Sherry_Daily/` and selects by date (the third-party
  `obsidian_get_recent_periodic_notes` is moot — route absent in v4.1.3).
- **Template expansion still needs Obsidian.** No MCP tool runs Templater directly, so
  resolving the Daily template uses the `obsidian://open?vault=<vault>&file=zz-Templates
  %2FDaily` URI (or a static Python port of the template when Obsidian is closed, e.g.
  unattended runs). `command_execute` may be able to trigger a Templater command instead
  — to be evaluated in planning (§12).

`config.yaml` selects the I/O mode (`obsidian.mode: mcp | filesystem`); collectors and
renderers call `obsidian.py` and stay agnostic to which is active.

**Registration, secret & TLS handling.** The `wp-labs-planner` plugin **bundles the MCP
server declaration** (plugin-root `.mcp.json`) as an HTTP server referencing
`${OBSIDIAN_API_KEY}` — no key committed:

```json
{ "mcpServers": { "obsidian": {
  "type": "http",
  "url": "https://127.0.0.1:27124/mcp/",
  "headers": { "Authorization": "Bearer ${OBSIDIAN_API_KEY}" } } } }
```

`.mcp.json` supports `${VAR}`/`${VAR:-default}` interpolation, but Claude Code reads the
value from the **shell environment at launch** — it does *not* auto-load a `.env`. So the
user exports `OBSIDIAN_API_KEY` (shell profile / `direnv`) before starting Claude.
*TLS:* the endpoint is HTTPS with a self-signed cert; Claude Code's HTTP MCP client must
trust it — point `NODE_EXTRA_CA_CERTS` at the plugin's cert (downloadable from
`GET /obsidian-local-rest-api.crt`) or enable the plugin's plain-HTTP port. The planner's
Python client trusts the same cert (never disables verification globally).

*Status in this environment:* native `/mcp/` validated end-to-end via direct HTTP
(initialize → session id, `tools/list` → 16 tools, read + reversible write). Bundled-
plugin MCP servers load in Claude only once the plugin is enabled and the session
reloads; the planner tooling drives the server directly regardless.

## 6. Behavior

### Daily (`python -m planner.daily`)
1. Read vault open tasks and state files, plus **recently-touched notes for context**
   (the minimum set): the past week's notes, yesterday's note, and any note modified the
   day before. Recency is detected by filesystem mtime; if the vault is a git repo, the
   collector also consults git history (e.g. `git log --since`) to confirm a note was
   genuinely just modified and to ignore incidental touch/sync changes.
2. Gmail: accomplishments = messages to `<user>+planner@<domain>` since the start of
   the current ISO week, excluding invites; upcoming calls = messages carrying
   calendar invites (`.ics`) or detected as meeting invites, future-dated.
3. Google Doc: fetch by ID → todo text.
4. OneNote: convert each configured `.one` file → Markdown.
5. Synthesis (`prompts/daily_synthesis.md`): produce the injected sections and assign a
   priority emoji to each new task.
6. Render: `render_daily.py` **expands the real Obsidian Daily template** (via the
   integration layer §5.2 — MCP/Local REST API preferred, `obsidian://open?vault=
   <vault>&file=zz-Templates%2FDaily` as fallback) so Templater resolves the tag, nav
   links, and Dataview blocks natively, rather than porting Templater in Python.
   It then injects content under `## Notes`:
   - **One `###` header per timed calendar event**, with a bullet underneath giving the
     event time and the `#project/<Name>` hashtag of the associated project (synthesis
     maps each event to a project via attendees/`#<company>/<first_last>` member tags or
     content). Untimed/all-day items are excluded. Directly beneath each event, a nested
     `#### Relevant previous summary for <event>` subsection surfaces the prior summary
     (from the recently-touched daily/weekly notes, §step 1) most relevant to that event.
   - `### ✅ This Week So Far` — synthesized accomplishments.
   - `### 📓 Learnings & Follow-ups` — from the converted OneNote notes.
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
   - a dated **timeline assessment** per project (how the project is tracking against
     its `## Timeline` — on track / slipping / blocked, with a brief rationale);
   - a static **grouped-by-project** todo snapshot (via the project list +
     `#project/<Name>` tags) with urgent items (🔺⏫) pinned to the top of each group.
3. Render `<weekly_dir>/YYYY-MM-DD-week-overview.md` (date = generation/Friday day) from
   the `Weekly.md` template:
   - Emit the template's Dataview `TASK` block **verbatim** (renders live in Obsidian:
     open tasks grouped by `#project/<Name>`, urgent-on-top).
   - **Underneath the Dataview**, write the static synthesized snapshot — the
     grouped-by-project todo list frozen at Friday + the per-project status lines — so
     the note is a permanent record alongside the live view. Each group is headed by a
     `[[00-<Name>|<Name>]]` link; frontmatter tagged `Weekly`.
   - For each project's `00-<Name>.md`, update two sections in place, newest-first and
     preserving prior entries (creating a section if absent): `## Status` gets the dated
     status line, and `## Timeline` gets the dated timeline assessment. Back up the
     project file before writing.

## 7. Config (`config.yaml` — paths/IDs only, no secrets)

- `google`: `credentials_path`, `token_path`, `planner_address`, `gdoc_id`
- `onenote`: list of `.one` paths, `converter_command`
- `vault`: vault path, `vault_name` (for the `obsidian://` URI, e.g. `szhou`),
  `templates_dir`, `projects_dir` (`00-InProgress`), `daily_output_dir`,
  `weekly_output_dir`, optional rolling todo/follow-up file paths
- `obsidian`: `mode` (`mcp` | `filesystem`) for note I/O; for `mcp`, the Local REST API
  host/port (token via the `OBSIDIAN_API_KEY` env/MCP config, never in this file)
- `llm`: `backend` (`claude` | `local`); for `claude`, the command (default `claude`)
  and flags; for `local`, the model name + endpoint/command (e.g. Ollama model + host)

## 8. OneNote conversion risk

Raw `.one` is undocumented binary — the single fragile piece. Conversion is a
**pluggable command** (`converter_command`) so the tool can be swapped without code
changes. The best-maintained `.one`→Markdown/HTML converter will be selected and its
install steps documented during planning. If conversion fails at runtime, the collector
logs a warning and the note shows a `⚠️ OneNote unavailable` placeholder.

## 9. Error handling

- Collectors are isolated: a failing/empty source degrades to a placeholder section;
  the run still produces a note.
- If the LLM backend fails (whichever is configured), the raw collected material is
  written under a banner so nothing is lost.
- Config is validated up front with actionable messages; auth failures print re-auth
  instructions.
- Vault writes (project `## Status`) back up the target file first.

## 10. Testing

Pytest mirroring module structure, with fixtures: sample Gmail API JSON, a
pre-converted OneNote fixture, sample Google Doc text, sample vault project notes and
task files. External APIs and the LLM backend (`claude -p` / local model) are mocked.
Coverage includes the happy path, a failing/empty source per collector, recent-note
selection (mtime + git-history fallback), daily render correctness (resolved tags, nav
links, verbatim Dataview blocks via template expansion, per-event `###` headers with
time + `#project/<Name>` plus a nested `#### Relevant previous summary` per event,
priority emojis), and weekly
correctness (static grouped-todo ordering, dated `## Status` and `## Timeline`
insertion, backup).

## 11. README / setup walkthrough

Bundled with the plugin and surfaced by `planner-setup`: Python/venv/deps → Google
Cloud OAuth client (Gmail + Docs scopes) → OneNote converter install → **LLM backend
setup** (default `claude -p`; or a local model — installing Ollama, pulling a model,
pointing `llm.backend: local` at it for fully offline runs) → `config.yaml` → vault
paths and template install → running each script manually → optional macOS `launchd`
schedule (daily + Friday weekly). The **Obsidian integration** step covers: installing
and enabling the Local REST API plugin (v4.x, with its built-in `/mcp/` server), copying
its API key, **exporting `OBSIDIAN_API_KEY`** in the shell (Claude Code does not auto-load
`.env`), and **trusting the self-signed cert** (`NODE_EXTRA_CA_CERTS` →
`/obsidian-local-rest-api.crt`, or enable the plain-HTTP port) so the plugin-bundled
native MCP server connects — or choosing `mode: filesystem` / `obsidian://` URI to skip
the MCP entirely.

## 12. Open items for planning

- Selection and install steps for the OneNote `.one` converter.
- Exact Gmail query/heuristics distinguishing accomplishment emails from invite emails.
- Whether `launchd` install is offered interactively by `planner-setup` or documented
  only.
- Recommended local model + runtime (e.g. Ollama model choice) and the prompt/output
  contract that keeps synthesis results consistent across the `claude` and `local`
  backends.
- Default Obsidian I/O mode (§5.2): `mcp` (mcp-obsidian + Local REST API) vs
  `filesystem`, and behavior for unattended/scheduled runs. Plus the template-expansion
  path when Obsidian is closed (URI requires it running; a static Python port is the
  offline fallback) — REST API/MCP cannot run Templater.
- ~~Version mismatch~~ **resolved**: use the plugin's native `/mcp/` server (§5.2)
  instead of third-party `mcp-obsidian`; recent-change/periodic gaps covered by
  `vault_read` stat / `search_query` / `periodic_note_get_path`.
- TLS trust for Claude Code's HTTP MCP client to the self-signed `/mcp/` endpoint
  (`NODE_EXTRA_CA_CERTS` vs enabling the plugin's plain-HTTP port) — pick the setup the
  `planner-setup` skill automates.
- Whether `command_execute` can trigger Templater daily-template expansion (removing the
  `obsidian://` URI dependency), vs the static Python-port fallback.
