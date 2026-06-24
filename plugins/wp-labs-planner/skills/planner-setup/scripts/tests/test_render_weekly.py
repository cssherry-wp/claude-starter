from __future__ import annotations

from datetime import date
from pathlib import Path

from planner.collectors.vault import Project
from planner.config import load_config
from planner.obsidian import FilesystemVault
from planner.render_weekly import build_weekly_body, decision_bullet, render_weekly, update_knowledge_bank, update_project_section

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def test_build_weekly_body_orders_urgent_first() -> None:
    synthesis = {
        "projects": [{"name": "VIP", "status": "on track", "timeline_assessment": "on track"}],
        "groups": [{"project": "VIP", "tasks": [
            {"text": "low one", "priority": "low"},
            {"text": "urgent one", "priority": "highest"},
        ]}],
    }
    body = build_weekly_body(synthesis, date(2026, 6, 26))
    assert "tags:" in body and "Weekly" in body
    assert "```dataview" in body
    assert "[[00-VIP|VIP]]" in body
    assert body.index("urgent one") < body.index("low one")


def test_update_project_section_creates_and_prepends() -> None:
    content = "# A5\n## Summary\n\n## TODO\n- [ ] x\n"
    out = update_project_section(content, "Status", "made progress", date(2026, 6, 26))
    assert "## Status" in out
    assert "- 2026-06-26 — made progress" in out
    assert out.index("## Status") < out.index("## TODO")


def test_render_weekly_writes_and_updates(tmp_path: Path) -> None:
    proj_dir = tmp_path / "00-InProgress" / "VIP"
    proj_dir.mkdir(parents=True)
    (proj_dir / "00-VIP.md").write_text("# VIP\n## Summary\n## Timeline\n## TODO\n")
    (tmp_path / "zz-Sherry_Weekly").mkdir()
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.obsidian.mode = "filesystem"
    v = FilesystemVault(str(tmp_path))
    projects = [Project("VIP", "00-InProgress/VIP/00-VIP.md", (proj_dir / "00-VIP.md").read_text())]
    synthesis = {"projects": [{"name": "VIP", "status": "shipped", "timeline_assessment": "on track"}],
                 "groups": []}
    touched = render_weekly(v, cfg, synthesis, projects, date(2026, 6, 26))
    assert any("week-overview" in p for p in touched)
    body = v.read("00-InProgress/VIP/00-VIP.md")
    assert "## Status" in body and "shipped" in body
    assert "## Timeline" in body and "on track" in body


def test_decision_bullet_links_to_header() -> None:
    b = decision_bullet({"decision": "Ship beta", "note": "zz-Sherry_Daily/2026-06-23.md",
                         "header": "Harlo testing"})
    assert b == "- Ship beta — [[2026-06-23#Harlo testing]]"
    b2 = decision_bullet({"decision": "Pick X", "note": "00-InProgress/VIP/Page.md", "header": ""})
    assert b2 == "- Pick X — [[Page]]"


def test_update_knowledge_bank_appends_dedups_newest_first() -> None:
    content = "# VIP\n## Summary\n\n## TODO\n- [ ] x\n"
    d1 = [{"decision": "Ship beta", "note": "a.md", "header": "H"}]
    out1 = update_knowledge_bank(content, d1)
    assert "## Knowledge Bank" in out1
    assert "- Ship beta — [[a#H]]" in out1
    assert out1.index("## Knowledge Bank") < out1.index("## TODO")
    # Re-run with one duplicate + one new -> only the new one is added, newest on top.
    d2 = [{"decision": "Ship beta", "note": "a.md", "header": "H"},
          {"decision": "Drop Y", "note": "b.md", "header": "H2"}]
    out2 = update_knowledge_bank(out1, d2)
    assert out2.count("Ship beta") == 1
    assert "Drop Y" in out2
    assert out2.index("Drop Y") < out2.index("Ship beta")
