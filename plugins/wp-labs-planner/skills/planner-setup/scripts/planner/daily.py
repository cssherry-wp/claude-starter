"""Entry point: build today's daily note."""
from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from planner import render_tasks
from planner.collectors import gmail, gsheet, onenote
from planner.collectors.vault import recent_notes
from planner.config import Config, load_config
from planner.errors import VaultIOError
from planner.gitcommit import commit_files, is_git_repo
from planner.obsidian import Vault, make_vault
from planner.people import match_people_tags, new_person_tags, parse_people_tags
from planner.render_daily import render_daily
from planner.synthesis import synthesize_daily

log = logging.getLogger(__name__)


def _load_prompt(name: str) -> str:
    return (Path(__file__).resolve().parent.parent / "templates" / "prompts" / name).read_text()


def _safe(label: str, fn: Callable[[], object]) -> object:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — resilience: degrade, never abort
        log.warning("daily collector '%s' failed: %s", label, exc)
        return f"⚠️ {label} unavailable"


def _safe_apply(label: str, fn: Callable[[], None]) -> None:
    """Call fn(); log a warning and continue if it raises — never abort the run.

    Args:
        label: Human-readable name for the apply step (used in the warning message).
        fn: Zero-argument callable to invoke.
    """
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 — resilience: degrade, never abort
        log.warning("daily apply '%s' failed: %s", label, exc)


def _gather_daily(vault: Vault, cfg: Config, today: date) -> dict:
    week_start = date.fromordinal(today.toordinal() - today.weekday())
    creds_holder: dict = {}

    def services() -> tuple:  # lazy: only authenticate if a Google collector runs
        if "g" not in creds_holder:
            creds = gmail.get_credentials(cfg.google, gmail.GMAIL_SCOPES)
            creds_holder["g"] = (gmail.build_gmail(creds), gmail.build_sheets(creds))
        return creds_holder["g"]

    def sheet_todos() -> dict:
        try:
            return gsheet.fetch_todos(services()[1], cfg.google.gdoc_id,
                                      cfg.google.overview_tab, cfg.google.weeks_back)
        except Exception as exc:  # noqa: BLE001 — degrade, never abort
            log.warning("daily collector 'gsheet' failed: %s", exc)
            return {"open": [], "completed": []}

    repo = cfg.vault.path if is_git_repo(cfg.vault.path) else None
    return {
        "accomplishments": _safe("gmail", lambda: gmail.fetch_accomplishments(
            services()[0], cfg.google.planner_address, week_start)),
        "calls": _safe("calls", lambda: [e.__dict__ for e in gmail.fetch_calls(
            services()[0], cfg.google.planner_address, today)]),
        "sheet": sheet_todos(),
        "onenote": _safe("onenote", lambda: "\n\n".join(
            onenote.convert(p, cfg.onenote.converter_command) for p in cfg.onenote.files)),
        "recent_notes": _safe("recent", lambda: [n.__dict__ for n in recent_notes(
            vault, cfg, today, repo)]),
    }


# Category prefix for attendees not yet in the People template; recategorize by hand.
_NEW_PERSON_PREFIX = "unsorted"


def _people_path(cfg: Config) -> str:
    return f"{cfg.vault.templates_dir}/People.md"


def _people_tags(vault: Vault, cfg: Config) -> list[str]:
    """Load the People template's hashtags from the vault, or [] if unavailable."""
    try:
        return parse_people_tags(vault.read(_people_path(cfg)))
    except VaultIOError:
        return []


def _resolve_people(vault: Vault, cfg: Config, fetched_calls: list[dict]) -> list[str]:
    """Return People tags, appending any new named attendees to the template first."""
    tags = _people_tags(vault, cfg)
    attendees = [a for call in fetched_calls for a in call.get("attendees", [])]
    new = new_person_tags(attendees, tags, _NEW_PERSON_PREFIX)
    if new:
        try:
            vault.append(_people_path(cfg), "\n".join(new) + "\n")
        except Exception as exc:  # noqa: BLE001 — never abort the run over a template write
            log.warning("could not add new people to %s: %s", _people_path(cfg), exc)
    return tags + new


def _merge_calls(fetched: list[dict], llm_calls: list[dict],
                 people_tags: list[str] | None = None) -> list[dict]:
    """Render events from the deterministically-parsed email, enriched by the LLM.

    Title and time come from fetch_calls (always present, correct local time). The
    LLM supplies project and a fallback summary, matched to the event by title.
    Attendees are matched against the People template to add person hashtags.

    Args:
        fetched: Event dicts parsed from the planner email (title, time, attendees).
        llm_calls: The LLM's calls output (title, project, previous_summary).
        people_tags: Hashtags from the People template for attendee matching.

    Returns:
        Merged call dicts shaped for build_notes_block.
    """
    enrichment = {c.get("title", ""): c for c in llm_calls}
    merged = []
    for event in fetched:
        extra = enrichment.get(event.get("title", ""), {})
        tags = match_people_tags(event.get("attendees", []), people_tags or [])
        merged.append({
            "title": event.get("title", ""),
            "time": event.get("time", ""),
            "project": extra.get("project", ""),
            "people": tags,
            "previous_summary": event.get("summary") or extra.get("previous_summary", ""),
        })
    return merged


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
    fetched_calls = payload.get("calls") or []
    if isinstance(fetched_calls, list):
        people = _resolve_people(vault, cfg, fetched_calls)
        synthesis["calls"] = _merge_calls(fetched_calls, synthesis.get("calls", []), people)
    path = render_daily(vault, cfg, synthesis, today)
    sheet = payload.get("sheet", {"open": [], "completed": []})
    index = render_tasks.existing_task_index(vault)
    _safe_apply("open items", lambda: render_tasks.apply_open_items(
        vault, cfg.vault.daily_output_dir, sheet["open"], today, index))
    sheet_keys = {render_tasks.normalize_text(o.text) for o in sheet["open"]}
    _safe_apply("llm tasks", lambda: render_tasks.apply_llm_tasks(
        vault, cfg.vault.daily_output_dir, synthesis.get("new_tasks", []), today, index, sheet_keys))
    _safe_apply("completed items", lambda: render_tasks.apply_completed_items(
        vault, cfg.vault.daily_output_dir, sheet["completed"], index))
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
