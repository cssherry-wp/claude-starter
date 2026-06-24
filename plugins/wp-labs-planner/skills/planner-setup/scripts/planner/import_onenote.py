"""On-demand importer: split a OneNote PDF into dated, versioned per-page notes."""
from __future__ import annotations

import argparse
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from planner.config import Config, load_config
from planner.onenote_notes import parse_note, render_note, sanitize_filename, versioned_note
from planner.onenote_pdf import OneNotePage, parse_pages, read_pdf_pages
from planner.synthesis import summarize_changes

log = logging.getLogger(__name__)
Summarize = Callable[[str, str], str]


def target_dir(page: OneNotePage, cfg: Config) -> tuple[Path, str | None]:
    """Return (absolute target dir, project name or None) for a page.

    Args:
        page: The OneNote page to map to a directory.
        cfg: The planner configuration.

    Returns:
        A tuple of (absolute directory path, project name or None).
        Project is None when the section has no mapping and falls back to import_dir.
    """
    root = Path(cfg.vault.path)
    project = cfg.onenote.section_to_project.get(page.section)
    if project:
        return root / cfg.vault.projects_dir / project, project
    log.warning("OneNote section %r unmapped; importing to %s/", page.section, cfg.onenote.import_dir)
    return root / cfg.onenote.import_dir / page.section, None


def set_mtime(path: Path, d: date) -> None:
    """Set a note's mtime to the page's edited date (noon, to avoid TZ edges).

    Args:
        path: The file path whose mtime to set.
        d: The date to set as the modification time.
    """
    ts = datetime(d.year, d.month, d.day, 12, 0).timestamp()
    os.utime(path, (ts, ts))


def import_page(page: OneNotePage, cfg: Config, summarize: Summarize) -> str:
    """Write or version one page note.

    Args:
        page: The OneNote page to import.
        cfg: The planner configuration.
        summarize: Callable(old_body, new_body) -> summary string (injected for testability).

    Returns:
        One of 'created', 'skipped', or 'updated'.
    """
    directory, project = target_dir(page, cfg)
    directory.mkdir(parents=True, exist_ok=True)
    note = directory / f"{sanitize_filename(page.title)}.md"
    if not note.exists():
        note.write_text(render_note(page, project), encoding="utf-8")
        if page.date:
            set_mtime(note, page.date)
        return "created"
    existing = note.read_text(encoding="utf-8")
    stored_date, _, old_body = parse_note(existing)
    if page.date and stored_date and page.date <= stored_date:
        return "skipped"
    try:
        summary = summarize(old_body, page.body)
    except Exception as exc:  # noqa: BLE001 — versioning must still advance
        log.warning("change summary failed for %s: %s", note.name, exc)
        summary = "_change summary unavailable_"
    note.write_text(versioned_note(existing, page, project, summary), encoding="utf-8")
    if page.date:
        set_mtime(note, page.date)
    return "updated"


def run_import(cfg: Config, pdf_path: str, summarize: Summarize) -> dict[str, int]:
    """Import every page of one PDF; return action counts.

    Args:
        cfg: The planner configuration.
        pdf_path: Path to the OneNote PDF file to import.
        summarize: Callable(old_body, new_body) -> summary string.

    Returns:
        Dict with counts for each action: {'created': n, 'skipped': n, 'updated': n}.
    """
    counts: dict[str, int] = {"created": 0, "skipped": 0, "updated": 0}
    for page in parse_pages(read_pdf_pages(pdf_path)):
        try:
            counts[import_page(page, cfg, summarize)] += 1
        except OSError as exc:  # skip a bad page, keep going
            log.warning("failed to import page %r: %s", page.title, exc)
    return counts


def main() -> None:
    """CLI entry point: python -m planner.import_onenote --pdf <file> [--config PATH]."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=os.environ.get("PLANNER_CONFIG", "config.yaml"))
    parser.add_argument("--pdf", action="append", help="PDF path (repeatable); defaults to config")
    args = parser.parse_args()
    cfg = load_config(args.config)
    pdfs = args.pdf or cfg.onenote.pdf
    prompt = _load_prompt("onenote_changes.md")

    def summarize(old: str, new: str) -> str:
        return summarize_changes(cfg.llm, prompt, old, new)

    for pdf in pdfs:
        print(pdf, run_import(cfg, pdf, summarize))


def _load_prompt(name: str) -> str:
    """Load a prompt template by name from the templates/prompts directory.

    Args:
        name: Filename of the prompt template (e.g. 'onenote_changes.md').

    Returns:
        The prompt template text.
    """
    return (Path(__file__).resolve().parent.parent / "templates" / "prompts" / name).read_text()


if __name__ == "__main__":
    main()
