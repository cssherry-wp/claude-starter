"""Entry point: build today's daily note."""
from __future__ import annotations

import argparse
import logging
import os
from datetime import date, datetime
from pathlib import Path

from planner.collectors import gdoc, gmail
from planner.collectors.vault import recent_notes
from planner.config import Config, load_config
from planner.gitcommit import commit_files, is_git_repo
from planner.obsidian import make_vault
from planner.render_daily import render_daily
from planner.synthesis import synthesize_daily

log = logging.getLogger(__name__)


def _load_prompt(name: str) -> str:
    return (Path(__file__).resolve().parent.parent / "templates" / "prompts" / name).read_text()


def _safe(label: str, fn) -> object:  # type: ignore[no-untyped-def]
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — resilience: degrade, never abort
        log.warning("daily collector '%s' failed: %s", label, exc)
        return f"⚠️ {label} unavailable"


def _gather_daily(vault, cfg: Config, today: date) -> dict:  # type: ignore[no-untyped-def]
    week_start = date.fromordinal(today.toordinal() - today.weekday())
    creds_holder: dict = {}

    def services() -> tuple:  # lazy: only authenticate if a Google collector runs
        if "g" not in creds_holder:
            creds = gmail.get_credentials(cfg.google, gmail.GMAIL_SCOPES)
            creds_holder["g"] = (gmail.build_gmail(creds), gmail.build_docs(creds))
        return creds_holder["g"]

    repo = cfg.vault.path if is_git_repo(cfg.vault.path) else None
    return {
        "accomplishments": _safe("gmail", lambda: gmail.fetch_accomplishments(
            services()[0], cfg.google.planner_address, week_start)),
        "calls": _safe("calls", lambda: [e.__dict__ for e in gmail.fetch_calls(
            services()[0], cfg.google.planner_address)]),
        "todos": _safe("gdoc", lambda: gdoc.fetch_todos(services()[1], cfg.google.gdoc_id)),
        "recent_notes": _safe("recent", lambda: [n.__dict__ for n in recent_notes(
            vault, cfg, today, repo)]),
    }


def run_daily(cfg: Config, today: date) -> str:
    """Gather → synthesize → render → commit; return the daily note path.

    Args:
        cfg: Loaded planner configuration.
        today: The date for which to build the daily note.

    Returns:
        Vault-relative path of the written daily note.
    """
    vault = make_vault(cfg)
    payload = _gather_daily(vault, cfg, today)
    synthesis = synthesize_daily(cfg.llm, _load_prompt("daily_synthesis.md"), payload)
    path = render_daily(vault, cfg, synthesis, today)
    if cfg.vault.git_commit and is_git_repo(cfg.vault.path):
        commit_files(cfg.vault.path, [str(Path(cfg.vault.path) / path)],
                     f"planner: daily {today.isoformat()}")
    return path


def main() -> None:
    """CLI entry: python -m planner.daily [--config PATH]."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=os.environ.get("PLANNER_CONFIG", "config.yaml"))
    args = parser.parse_args()
    cfg = load_config(args.config)
    print(run_daily(cfg, datetime.now().date()))


if __name__ == "__main__":
    main()
