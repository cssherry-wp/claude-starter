---
name: planner-setup
description: Check whether the wp-labs-planner is installed/configured/scheduled and, if not, walk the user through setup (Python env, Google OAuth, OneNote converter, LLM backend, Obsidian Local REST API + key, templates, schedule).
---

# Planner Setup

Use when the user wants to install, configure, or check the status of the wp-labs-planner.

## Steps

1. **Run the status check.** From `${CLAUDE_PLUGIN_ROOT}/skills/planner-setup`:
   `python3 status_check.py <config_path>` (default `config.yaml`). Report each flag.
2. **For each unmet flag, walk the fix** (idempotent — safe to re-run):
   - `config_present`/`config_valid`: copy `scripts/templates/config.example.yaml` to the
     user's `config.yaml`; fill `planner_address`, `gdoc_id`, vault paths.
   - `token_present`: have them create a Google Cloud OAuth desktop client (Gmail +
     Docs read-only scopes), save `credentials.json`, then run `python -m planner.daily`
     once to trigger the consent flow (writes `token.json`).
   - `obsidian_env_set`: install + enable the Obsidian **Local REST API** plugin, copy
     its API key, and `export OBSIDIAN_API_KEY=<key>` in the shell profile. Trust the
     self-signed cert (download from `https://127.0.0.1:27124/obsidian-local-rest-api.crt`
     into `obsidian.cert_path`, or set `NODE_EXTRA_CA_CERTS` for the bundled MCP server).
   - `vault_reachable`: verify `vault.path`; copy `scripts/templates/Daily.md` and
     `scripts/templates/Weekly.md` into `vault/<templates_dir>`.
   - OneNote: export the notebook to PDF, set `onenote.pdf` + `onenote.section_to_project`, and run `python -m planner.import_onenote` to import pages into project folders.
   - LLM backend: see README.
3. **Offer scheduling** (optional): install the launchd plists from
   `scripts/templates/launchd/` (daily, plus weekly on Fridays).
4. **Confirm:** re-run `status_check.py`; "running" = all flags except optional schedule.
