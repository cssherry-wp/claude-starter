from __future__ import annotations

from datetime import date
from pathlib import Path

import planner.daily as daily_mod
import planner.weekly as weekly_mod
from planner.config import load_config
from planner.obsidian import FilesystemVault

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def test_consolidate_knowledge_updates_index(tmp_path, monkeypatch) -> None:
    proj = tmp_path / "00-InProgress" / "VIP"
    proj.mkdir(parents=True)
    (proj / "00-VIP.md").write_text("# VIP\n## Summary\n## TODO\n")
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.obsidian.mode = "filesystem"
    import planner.weekly as wk
    from planner.collectors.vault import Material, Project
    from planner.obsidian import FilesystemVault
    monkeypatch.setattr(wk, "attribute_material",
                        lambda v, c, t, r: {"VIP": [Material("VIP", "a.md", "H", "decided X")]})
    monkeypatch.setattr(wk, "extract_decisions",
                        lambda cfg, tmpl, project, materials:
                        [{"decision": "Do X", "note": "a.md", "header": "H"}])
    v = FilesystemVault(str(tmp_path))
    projects = [Project("VIP", "00-InProgress/VIP/00-VIP.md", (proj / "00-VIP.md").read_text())]
    touched = wk.consolidate_knowledge(v, cfg, projects, date(2026, 6, 26))
    body = (proj / "00-VIP.md").read_text()
    assert "## Knowledge Bank" in body and "Do X" in body and "[[a#H]]" in body
    assert any("00-VIP.md" in p for p in touched)


def test_run_daily_end_to_end(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "zz-Sherry_Daily").mkdir()
    (tmp_path / "zz-Sherry_Daily" / "2026-06-23.md").write_text("## Notes\n\n## TODO\n")
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.obsidian.mode = "filesystem"
    cfg.vault.git_commit = False

    monkeypatch.setattr(daily_mod, "make_vault", lambda c: FilesystemVault(str(tmp_path)))
    monkeypatch.setattr(daily_mod, "_gather_daily", lambda vault, cfg, today: {"x": 1})
    monkeypatch.setattr(daily_mod, "synthesize_daily",
                        lambda cfg, tmpl, payload: {"calls": [], "accomplishments_md": "- a",
                                                    "learnings_md": "", "new_tasks": []})
    path = daily_mod.run_daily(cfg, date(2026, 6, 23))
    assert path.endswith("2026-06-23.md")
    assert "### ✅ This Week So Far" in (tmp_path / "zz-Sherry_Daily" / "2026-06-23.md").read_text()


def test_run_weekly_end_to_end(tmp_path: Path, monkeypatch) -> None:
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.obsidian.mode = "filesystem"
    cfg.vault.git_commit = False
    monkeypatch.setattr(weekly_mod, "make_vault", lambda c: FilesystemVault(str(tmp_path)))
    monkeypatch.setattr(weekly_mod, "_gather_weekly", lambda vault, cfg: ({"projects": [], "open_tasks": []}, []))
    monkeypatch.setattr(weekly_mod, "synthesize_weekly", lambda cfg, tmpl, payload: {"projects": [], "groups": []})
    monkeypatch.setattr(weekly_mod, "consolidate_knowledge", lambda vault, cfg, projects, today: [])
    touched = weekly_mod.run_weekly(cfg, date(2026, 6, 26))
    assert any("week-overview" in p for p in touched)
    body = FilesystemVault(str(tmp_path)).read("zz-Sherry_Weekly/2026-06-26-week-overview.md")
    assert "Weekly" in body
