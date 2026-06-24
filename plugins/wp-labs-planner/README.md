# wp-labs-planner Setup

Daily & weekly Obsidian planner that aggregates Gmail (+planner alias), a Google Doc, OneNote, and vault state into Obsidian notes via the Local REST API MCP.

## Prerequisites

- Python ≥ 3.11
- `uv` (package manager)

## Installation

1. **Set up the Python environment:**
   ```bash
   uv venv
   uv pip install -e ".[dev]"
   ```

2. **Create a Google Cloud OAuth desktop client:**
   - Enable the **Gmail API** and **Google Docs API** in your Google Cloud project
   - Enable Gmail and Google Docs (read-only) scopes
   - Download the JSON credentials
   - Save as `credentials.json` in the scripts directory
   - Run `python -m planner.daily` once to trigger the consent flow (writes `token.json`)

3. **Configure the planner:**
   - Copy `scripts/templates/config.example.yaml` to `config.yaml`
   - Fill in:
     - `planner_address`: Gmail alias (e.g., `planner@mydomain.com`)
     - `gdoc_id`: Google Doc ID for todos
     - `vault.path`: path to Obsidian vault
     - `vault.templates_dir`: where to find/copy templates
     - `obsidian.api_key` / `obsidian.cert_path` (or use env var)
   - Copy `scripts/templates/Daily.md` and `scripts/templates/Weekly.md` into `vault/<templates_dir>`

4. **Configure LLM backend:**
   - Default: `claude -p` (Claude via Claude Code)
   - Alternative (local): set in `config.yaml`:
     ```yaml
     llm:
       backend: local
       model: neural-chat
       endpoint: http://localhost:11434
     ```

5. **Set up Obsidian Local REST API:**
   - Install the **Obsidian Local REST API** plugin via Community Plugins
   - Enable it and copy the API key
   - Add to shell profile (`.zshenv`, `.bashrc`, etc.):
     ```bash
     export OBSIDIAN_API_KEY=<key>
     ```
   - Trust the self-signed certificate:
     - Download from `https://127.0.0.1:27124/obsidian-local-rest-api.crt` (default port; adjust if you changed it in the plugin settings) and save to `obsidian.cert_path` in config
     - Or set `NODE_EXTRA_CA_CERTS` for the bundled MCP server

## Running

Replace `/path/to/wp-labs-planner/skills/planner-setup` with your installed plugin path. The `scripts/` directory is the planner tool directory (contains `pyproject.toml`).

**Daily planner:**
```bash
cd /path/to/wp-labs-planner/skills/planner-setup/scripts
python -m planner.daily --config /path/to/config.yaml
```

**Weekly planner (Fridays):**
```bash
cd /path/to/wp-labs-planner/skills/planner-setup/scripts
python -m planner.weekly --config /path/to/config.yaml
```

## Importing OneNote

The planner can import pages from a OneNote notebook exported to PDF. Pages are organized into project folders based on the section name, with unmapped sections falling back to a configurable import directory.

**Setup:**
1. Export your OneNote notebook to PDF (File > Export / Print to PDF)
2. In `config.yaml`, set `onenote.pdf` to the exported PDF path and `onenote.section_to_project` to map section names to project folders:
   ```yaml
   onenote:
     pdf:
       - ~/OneDrive/Notebooks/AI Value Creation.pdf
     section_to_project:
       "UVEX (Hexarmor)": Hexarmor
       "Example-Infinite": Infinite
     import_dir: OneNote
   ```
3. Run the importer:
   ```bash
   cd /path/to/wp-labs-planner/skills/planner-setup/scripts
   python -m planner.import_onenote --pdf "/path/to/notebook.pdf"
   ```

**How it works:**
- Each page becomes a note in its mapped project folder (or `<import_dir>/<Section>/` if unmapped)
- The note includes the page's edited date as a frontmatter tag and file modification time
- Re-importing a newer export of the same page prepends a `## Changes - #<new> from #<old>` block to track revisions
- The weekly run grows each project's `## Knowledge Bank` with new material from the imported pages

## Scheduling (Optional)

Install launchd plists for automatic daily & weekly runs:

1. Copy `scripts/templates/launchd/com.wp-labs.planner.daily.plist` to `~/Library/LaunchAgents/`
2. Copy `scripts/templates/launchd/com.wp-labs.planner.weekly.plist` to `~/Library/LaunchAgents/`
3. Update `/PATH/TO/scripts` and `/PATH/TO/config.yaml` in both plists
4. Ensure your shell profile (`.zshenv`) exports `OBSIDIAN_API_KEY` for unattended runs
5. Load the services (macOS 13+):
   ```bash
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.wp-labs.planner.daily.plist
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.wp-labs.planner.weekly.plist
   ```
   To unload: `launchctl bootout gui/$(id -u)/com.wp-labs.planner.daily` and `launchctl bootout gui/$(id -u)/com.wp-labs.planner.weekly`

Logs go to `/tmp/planner.daily.log` and `/tmp/planner.weekly.log`.

## Setup Skill

Run the `planner-setup` skill in Claude Code to check & install all prerequisites interactively.
