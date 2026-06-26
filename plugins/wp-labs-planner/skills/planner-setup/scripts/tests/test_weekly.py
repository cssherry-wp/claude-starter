from __future__ import annotations

from datetime import date
from pathlib import Path

from planner.config import load_config
from planner.obsidian import FilesystemVault
from planner.weekly import _gather_weekly

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def test_gather_weekly_includes_week_dailies(tmp_path: Path) -> None:
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.obsidian.mode = "filesystem"
    daily_dir = tmp_path / cfg.vault.daily_output_dir
    daily_dir.mkdir(parents=True)
    (daily_dir / "2026-06-23.md").write_text("# 2026-06-23\n## Notes\nLearned X\n")
    vault = FilesystemVault(str(tmp_path))

    payload, _ = _gather_weekly(vault, cfg, date(2026, 6, 24))

    names = [d["name"] for d in payload["dailies"]]
    assert "2026-06-23" in names
    assert any("Learned X" in d["content"] for d in payload["dailies"])


def test_gather_weekly_includes_notes_dir(tmp_path: Path) -> None:
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.obsidian.mode = "filesystem"
    cfg.vault.notes_dir = "Notes"
    (tmp_path / "Notes").mkdir()
    (tmp_path / "Notes" / "research.md").write_text("# research\nfindings\n")
    vault = FilesystemVault(str(tmp_path))

    payload, _ = _gather_weekly(vault, cfg, date(2026, 6, 24))

    names = [n["name"] for n in payload["notes"]]
    assert "research" in names
