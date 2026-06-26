from __future__ import annotations

from datetime import date
from pathlib import Path

from planner.config import load_config
from planner.obsidian import FilesystemVault
from planner.render_daily import build_notes_block, render_daily

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def test_build_notes_block_renders_events_only_not_summary_or_tasks() -> None:
    synthesis = {
        "calls": [{"title": "Sync", "time": "15:00", "project": "#project/VIP",
                   "previous_summary": "last sync agreed on scope"}],
        "accomplishments_md": "- shipped",
        "learnings": [{"text": "learned x", "source": "2026-06-22", "header": ""}],
        "new_tasks": [{"text": "follow up", "priority": "high"}],
    }
    block = build_notes_block(synthesis)
    assert "### Sync [[00-VIP|VIP]]" in block  # project is a clickable note link on the header
    assert "- 15:00" in block
    # the relevant prior context sits as a plain bullet under the time line, no subheader
    assert "- last sync agreed on scope" in block
    assert "#### Relevant previous summary" not in block
    assert block.index("- 15:00") < block.index("- last sync agreed on scope")
    # summary sections and tasks are rendered elsewhere (their own ## sections / ## New open items)
    assert "Learnings & Follow-ups" not in block
    assert "This Week So Far" not in block
    assert "- [ ] follow up" not in block


def test_build_notes_block_renders_people_section() -> None:
    synthesis = {
        "calls": [{"title": "Demo Hour", "time": "18:00", "project": "#project/VIP",
                   "people": ["#wpl/sherry", "#vip/ray_rouleau"], "previous_summary": ""}],
        "accomplishments_md": "", "learnings": [], "new_tasks": [],
    }
    block = build_notes_block(synthesis)
    assert "### Demo Hour [[00-VIP|VIP]]" in block  # project linked on the heading
    assert "#### People for Demo Hour" in block
    assert "- #wpl/sherry" in block and "- #vip/ray_rouleau" in block
    # people come after the time line
    assert block.index("- 18:00") < block.index("#### People for Demo Hour")


def test_build_notes_block_tags_time_line_with_project() -> None:
    synthesis = {"calls": [{"title": "Sync", "time": "15:00", "project": "#project/VIP"}]}
    block = build_notes_block(synthesis)
    assert "- 15:00 #project/VIP" in block


def test_build_notes_block_time_line_without_project() -> None:
    synthesis = {"calls": [{"title": "Sync", "time": "15:00", "project": ""}]}
    block = build_notes_block(synthesis)
    assert "- 15:00" in block and "#project/" not in block


def test_build_notes_block_links_header_project_keeps_time_tag() -> None:
    synthesis = {"calls": [{"title": "Sync", "time": "15:00", "project": "#project/VIP"}]}
    block = build_notes_block(synthesis)
    assert "### Sync [[00-VIP|VIP]]" in block      # header links to the project note
    assert "- 15:00 #project/VIP" in block          # time line keeps the tag for Dataview


def test_build_notes_block_renders_video_join_link_under_header() -> None:
    synthesis = {"calls": [{"title": "Sync", "time": "15:00", "project": "#project/VIP",
                            "video_url": "https://wp.zoom.us/j/42"}]}
    block = build_notes_block(synthesis)
    assert "- [Join Zoom](https://wp.zoom.us/j/42)" in block
    # the join link sits directly under the header, above the time line
    assert block.index("Join Zoom") < block.index("- 15:00")


def test_build_notes_block_no_join_link_when_absent() -> None:
    synthesis = {"calls": [{"title": "Sync", "time": "15:00", "project": "#project/VIP"}]}
    block = build_notes_block(synthesis)
    assert "Join" not in block


def test_render_daily_injects(tmp_path: Path) -> None:
    daily = tmp_path / "zz-Sherry_Daily"
    daily.mkdir()
    # note created from the template: New open items sits above the summary sections
    (daily / "2026-06-23.md").write_text(
        "## Notes\n\n## New open items\n\n## ✅ This Week So Far\n\n"
        "## 📓 Learnings & Follow-ups\n\n## TODO\n")
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.obsidian.mode = "filesystem"
    v = FilesystemVault(str(tmp_path))
    synthesis = {"calls": [], "accomplishments_md": "- a",
                 "learnings": [{"text": "watch the rollout", "source": "2026-06-22",
                                "header": "Learnings"}],
                 "new_tasks": []}
    path = render_daily(v, cfg, synthesis, date(2026, 6, 23))
    body = v.read("zz-Sherry_Daily/2026-06-23.md")
    assert path.endswith("2026-06-23.md")
    assert "## ✅ This Week So Far" in body and "- a" in body
    # New open items stays above the weekly summary; summary stays above TODO
    assert body.index("## New open items") < body.index("## ✅ This Week So Far")
    assert body.index("## ✅ This Week So Far") < body.index("## TODO")
    # learnings link back to their source daily note
    assert "- watch the rollout ([[2026-06-22#Learnings]])" in body
