"""Entry point: build the weekly overview (run on Friday)."""
from __future__ import annotations

import argparse
import logging
import os
from datetime import date, datetime
from pathlib import Path

from planner.collectors.vault import attribute_material, list_projects, open_tasks
from planner.collectors.vault import Project
from planner.config import Config, load_config
from planner.gitcommit import commit_files, is_git_repo
from planner.obsidian import Vault, make_vault
from planner.render_weekly import render_weekly, update_knowledge_bank
from planner.synthesis import extract_decisions, synthesize_weekly

log = logging.getLogger(__name__)


def _load_prompt(name: str) -> str:
    return (Path(__file__).resolve().parent.parent / "templates" / "prompts" / name).read_text()


def _safe(label: str, fn) -> object:  # type: ignore[no-untyped-def]
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — resilience
        log.warning("weekly collector '%s' failed: %s", label, exc)
        return []


def _gather_weekly(vault, cfg: Config) -> tuple[dict, list]:  # type: ignore[no-untyped-def]
    projects: list = _safe("list_projects", lambda: list_projects(vault, cfg)) or []  # type: ignore[assignment]
    payload = {
        "projects": [{"name": p.name, "content": p.content} for p in projects],
        "open_tasks": [t.__dict__ for t in (_safe("tasks", lambda: open_tasks(vault, cfg)) or [])],  # type: ignore[attr-defined]
    }
    return payload, projects


def consolidate_knowledge(vault: Vault, cfg: Config, projects: list[Project], today: date) -> list[str]:
    """Update each project's ## Knowledge Bank from this week's attributed material.

    Args:
        vault: The vault to read from and write to.
        cfg: Loaded planner configuration.
        projects: List of Project objects to update.
        today: The reference date for recent-material attribution.

    Returns:
        List of vault-relative paths that were written (one per updated project).
    """
    repo = cfg.vault.path if is_git_repo(cfg.vault.path) else None
    by_project = attribute_material(vault, cfg, today, repo)
    prompt = _load_prompt("decisions.md")
    touched: list[str] = []
    for proj in projects:
        mats = by_project.get(proj.name, [])
        if not mats:
            continue
        try:
            decisions = extract_decisions(
                cfg.llm, prompt, proj.name,
                [{"note": m.note_path, "header": m.header, "text": m.text} for m in mats])
            content = vault.read(proj.path)
            vault.write(proj.path, update_knowledge_bank(content, decisions))
            touched.append(proj.path)
        except Exception as exc:  # noqa: BLE001 — one project must not abort the run
            log.warning("knowledge bank update failed for %s: %s", proj.name, exc)
    return touched


def run_weekly(cfg: Config, gen_day: date) -> list[str]:
    """Gather → synthesize → render → commit; return touched paths.

    Args:
        cfg: Loaded planner configuration.
        gen_day: The date for which the weekly overview is generated.

    Returns:
        List of vault-relative paths that were written.
    """
    vault = make_vault(cfg)
    payload, projects = _gather_weekly(vault, cfg)
    synthesis = synthesize_weekly(cfg.llm, _load_prompt("weekly_synthesis.md"), payload)
    touched = render_weekly(vault, cfg, synthesis, projects, gen_day)
    touched += consolidate_knowledge(vault, cfg, projects, gen_day)
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
