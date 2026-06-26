"""Entry point: build the weekly overview (run on Friday)."""
from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from planner.collectors.vault import list_projects, notes_under, open_tasks, recent_notes
from planner.config import Config, load_config
from planner.gitcommit import commit_files, is_git_repo
from planner.obsidian import Vault, make_vault
from planner.render_weekly import render_weekly
from planner.synthesis import synthesize_weekly

log = logging.getLogger(__name__)


def _load_prompt(name: str) -> str:
    return (Path(__file__).resolve().parent.parent / "templates" / "prompts" / name).read_text()


def _safe(label: str, fn: Callable[[], object]) -> object:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — resilience
        log.warning("weekly collector '%s' failed: %s", label, exc)
        return []


def _gather_weekly(vault: Vault, cfg: Config, gen_day: date) -> tuple[dict, list]:
    projects: list = _safe("list_projects", lambda: list_projects(vault, cfg)) or []  # type: ignore[assignment]
    repo = cfg.vault.path if is_git_repo(cfg.vault.path) else None
    dailies: list = _safe(  # type: ignore[assignment]
        "dailies", lambda: recent_notes(vault, cfg, gen_day, repo)) or []
    notes: list = _safe("notes", lambda: notes_under(vault, cfg)) or []  # type: ignore[assignment]
    payload = {
        "projects": [{"name": p.name, "content": p.content} for p in projects],
        "open_tasks": [t.__dict__ for t in (_safe("tasks", lambda: open_tasks(vault, cfg)) or [])],  # type: ignore[attr-defined]
        "dailies": [{"name": Path(n.path).stem, "content": n.content} for n in dailies],  # type: ignore[attr-defined]
        "notes": [{"name": Path(n.path).stem, "content": n.content} for n in notes],  # type: ignore[attr-defined]
    }
    return payload, projects


def run_weekly(cfg: Config, gen_day: date) -> list[str]:
    """Gather → synthesize → render → commit; return touched paths.

    Args:
        cfg: Loaded planner configuration.
        gen_day: The date for which the weekly overview is generated.

    Returns:
        List of vault-relative paths that were written.
    """
    vault = make_vault(cfg)
    payload, projects = _gather_weekly(vault, cfg, gen_day)
    synthesis = synthesize_weekly(cfg.llm, _load_prompt("weekly_synthesis.md"), payload)
    touched = render_weekly(vault, cfg, synthesis, projects, gen_day)
    if cfg.vault.git_commit and is_git_repo(cfg.vault.path):
        commit_files(cfg.vault.path, [str(Path(cfg.vault.path) / p) for p in touched],
                     f"planner: weekly overview {gen_day.isoformat()}")
    return touched


def main() -> None:
    """CLI entry: python -m planner.weekly [--config PATH]."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=os.environ.get("PLANNER_CONFIG", "config.yaml"))
    args = parser.parse_args()
    cfg = load_config(args.config)
    for path in run_weekly(cfg, datetime.now().date()):
        print(path)


if __name__ == "__main__":
    main()
