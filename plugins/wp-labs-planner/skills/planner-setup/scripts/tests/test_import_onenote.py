from __future__ import annotations

import datetime as dt
from datetime import date
from pathlib import Path

from planner.config import load_config
from planner.import_onenote import import_page, target_dir
from planner.onenote_pdf import OneNotePage

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def cfg_for(tmp_path: Path):
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.onenote.section_to_project = {"UVEX (Hexarmor)": "Hexarmor"}
    cfg.onenote.import_dir = "OneNote"
    (tmp_path / "00-InProgress" / "Hexarmor").mkdir(parents=True)
    return cfg


def test_target_dir_mapped_vs_fallback(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    d_map, proj = target_dir(OneNotePage("UVEX (Hexarmor)", "T", date(2026, 5, 26), ""), cfg)
    assert proj == "Hexarmor" and d_map.as_posix().endswith("00-InProgress/Hexarmor")
    d_fb, proj2 = target_dir(OneNotePage("WP Labs", "T", date(2026, 5, 26), ""), cfg)
    assert proj2 is None and d_fb.as_posix().endswith("OneNote/WP Labs")


def test_import_page_created_then_skipped_then_updated(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    page = OneNotePage("UVEX (Hexarmor)", "Harlo testing", date(2026, 5, 26), "v1 body")
    assert import_page(page, cfg, lambda old, new: "summary") == "created"
    note = tmp_path / "00-InProgress" / "Hexarmor" / "Harlo testing.md"
    assert note.is_file()
    assert "v1 body" in note.read_text()
    # mtime set to the page date (2026-05-26).
    assert dt.date.fromtimestamp(note.stat().st_mtime) == date(2026, 5, 26)
    # Same date again -> skipped.
    assert import_page(page, cfg, lambda old, new: "summary") == "skipped"
    # Newer date -> updated with a prepended changes block + replaced body.
    newer = OneNotePage("UVEX (Hexarmor)", "Harlo testing", date(2026, 6, 10), "v2 body")
    assert import_page(newer, cfg, lambda old, new: "Added X") == "updated"
    text = note.read_text()
    assert "## Changes - #2026/06/10 from #2026/05/26" in text
    assert "Added X" in text and "v2 body" in text
    assert dt.date.fromtimestamp(note.stat().st_mtime) == date(2026, 6, 10)


def test_import_page_summary_failure_still_versions(tmp_path: Path) -> None:
    cfg = cfg_for(tmp_path)
    page = OneNotePage("UVEX (Hexarmor)", "Harlo testing", date(2026, 5, 26), "v1 body")
    assert import_page(page, cfg, lambda old, new: "ok") == "created"

    def boom(old: str, new: str) -> str:
        raise RuntimeError("llm down")

    newer = OneNotePage("UVEX (Hexarmor)", "Harlo testing", date(2026, 6, 10), "v2 body")
    assert import_page(newer, cfg, boom) == "updated"
    text = (tmp_path / "00-InProgress" / "Hexarmor" / "Harlo testing.md").read_text()
    assert "_change summary unavailable_" in text
    assert "## Changes - #2026/06/10 from #2026/05/26" in text
    assert "v2 body" in text
