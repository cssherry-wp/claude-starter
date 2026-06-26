# wp-labs-planner Setup

Daily & weekly Obsidian planner that aggregates Gmail (+planner alias), a Google Sheet (`Overview` tab), OneNote, and vault state into Obsidian notes via the Local REST API MCP.

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
   - Enable the **Gmail API** and **Google Sheets API** in your Google Cloud project
   - Enable Gmail (`gmail.readonly`) and Google Sheets (`spreadsheets.readonly`) scopes
   - Download the JSON credentials
   - Save as `credentials.json` in the scripts directory
   - Run `python -m planner.daily` once to trigger the consent flow (writes `token.json`)

3. **Install & configure OneNote converter:**
   - Install a OneNote-to-Markdown converter (e.g., `pandoc`, `mammoth`, or similar)
   - Set `converter_command` in `config.yaml` with placeholders `{input}` and `{output}`:
     ```yaml
     converter_command: "pandoc {input} -t markdown -o {output}"
     ```
   - On converter failure, planner falls back to a placeholder note

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

6. **Configure the planner:**
   - Copy `scripts/templates/config.example.yaml` to `config.yaml`
   - Fill in:
     - `planner_address`: Gmail alias (e.g., `planner@mydomain.com`)
     - `gdoc_id`: Google Sheet URL or spreadsheet ID for the Overview tab todos
     - `vault.path`: path to Obsidian vault
     - `vault.templates_dir`: where to find/copy templates
     - `obsidian.api_key` / `obsidian.cert_path` (or use env var)
   - Copy `scripts/templates/Daily.md` and `scripts/templates/Weekly.md` into `vault/<templates_dir>`

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
