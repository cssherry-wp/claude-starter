from __future__ import annotations

from datetime import date
from pathlib import Path

from planner.config import load_config
from planner.obsidian import FilesystemVault
from planner.render_daily import build_notes_block, render_daily

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def test_build_notes_block_has_event_sections_but_not_tasks() -> None:
    synthesis = {
        "calls": [{"title": "Sync", "time": "15:00", "project": "#project/VIP",
                   "previous_summary": "last sync agreed on scope"}],
        "accomplishments_md": "- shipped",
        "learnings_md": "- learned x",
        "new_tasks": [{"text": "follow up", "priority": "high"}],
    }
    block = build_notes_block(synthesis)
    assert "### Sync #project/VIP" in block
    assert "- 15:00" in block
    assert "#### Relevant previous summary for Sync" in block
    assert "### 📓 Learnings & Follow-ups" in block
    assert "### ✅ This Week So Far" in block
    # new_tasks are no longer rendered under Notes — they route to ## Open Items via apply_llm_tasks
    assert "- [ ] follow up" not in block


def test_build_notes_block_renders_people_section() -> None:
    synthesis = {
        "calls": [{"title": "Demo Hour", "time": "18:00", "project": "#project/VIP",
                   "people": ["#wpl/sherry", "#vip/ray_rouleau"], "previous_summary": ""}],
        "accomplishments_md": "", "learnings_md": "", "new_tasks": [],
    }
    block = build_notes_block(synthesis)
    assert "### Demo Hour #project/VIP" in block  # tags no longer on the heading
    assert "#### People for Demo Hour" in block
    assert "- #wpl/sherry" in block and "- #vip/ray_rouleau" in block
    # people appear after the time, before any summary
    assert block.index("- 18:00") < block.index("#### People for Demo Hour")


def test_render_daily_injects(tmp_path: Path) -> None:
    daily = tmp_path / "zz-Sherry_Daily"
    daily.mkdir()
    (daily / "2026-06-23.md").write_text("## Notes\n\n## TODO\n")
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.obsidian.mode = "filesystem"
    v = FilesystemVault(str(tmp_path))
    synthesis = {"calls": [], "accomplishments_md": "- a", "learnings_md": "", "new_tasks": []}
    path = render_daily(v, cfg, synthesis, date(2026, 6, 23))
    body = v.read("zz-Sherry_Daily/2026-06-23.md")
    assert path.endswith("2026-06-23.md")
    assert "### ✅ This Week So Far" in body
    assert body.index("### ✅ This Week So Far") < body.index("## TODO")
