from __future__ import annotations

from datetime import date
from pathlib import Path

from planner.collectors.vault import Project
from planner.config import load_config
from planner.obsidian import FilesystemVault
from planner.render_weekly import (
    _highlights_block,
    _learnings_block,
    _open_tasks_block,
    build_weekly_body,
    load_default_weekly_template,
    render_weekly,
    update_project_section,
)

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def test_highlights_block_renders_bullets() -> None:
    block = _highlights_block({"highlights": ["Shipped onboarding", "Closed Q2 audit"]})
    assert block == "- Shipped onboarding\n- Closed Q2 audit"


def test_highlights_block_empty_when_absent() -> None:
    assert _highlights_block({}) == ""
    assert _highlights_block({"highlights": ["", "  "]}) == ""


def test_open_tasks_block_has_status_bullets_then_ordered_tasks() -> None:
    synthesis = {
        "projects": [{"name": "VIP", "status": "shipped beta", "timeline_assessment": "on track"}],
        "groups": [{"project": "VIP", "tasks": [
            {"text": "low one", "priority": "low"},
            {"text": "urgent one", "priority": "highest"},
        ]}],
    }
    block = _open_tasks_block(synthesis)
    assert "### [[00-VIP|VIP]]" in block
    assert "- **Status:** shipped beta" in block
    assert "- **Timeline:** on track" in block
    # status bullets precede the tasks; urgent precedes low
    assert block.index("**Status:**") < block.index("urgent one")
    assert block.index("urgent one") < block.index("low one")


def test_open_tasks_block_omits_blank_status() -> None:
    synthesis = {"projects": [{"name": "VIP"}],
                 "groups": [{"project": "VIP", "tasks": [{"text": "t", "priority": "high"}]}]}
    block = _open_tasks_block(synthesis)
    assert "**Status:**" not in block and "**Timeline:**" not in block
    assert "- [ ] t" in block


def test_learnings_block_links_to_source_daily() -> None:
    block = _learnings_block({"learnings": [
        {"text": "Cache cut latency", "source": "2026-06-23"},
        {"text": "Follow up with vendor", "source": ""},
        {"text": "  ", "source": "2026-06-22"},
    ]})
    assert block == "- Cache cut latency ([[2026-06-23]])\n- Follow up with vendor"


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


def test_build_weekly_body_fills_template_token_and_sections() -> None:
    template = ("# Week overview — {{week}}\n\n## Snapshot (frozen)\n\n"
                "## Project statuses\n\n## References\n")
    synthesis = {
        "projects": [{"name": "VIP", "status": "shipped"}],
        "groups": [{"project": "VIP", "tasks": [{"text": "do it", "priority": "high"}]}],
    }
    body = build_weekly_body(synthesis, date(2026, 6, 26), template)
    assert "# Week overview — 2026-06-26" in body and "{{week}}" not in body
    # snapshot lands under its heading, before Project statuses
    assert body.index("[[00-VIP|VIP]]") < body.index("## Project statuses")
    assert "- **[[00-VIP|VIP]]** — shipped" in body
    assert "## References" in body  # untouched static section preserved


def test_render_weekly_prefers_vault_template(tmp_path: Path) -> None:
    (tmp_path / "zz-Sherry_Weekly").mkdir()
    (tmp_path / "zz-Templates").mkdir()
    (tmp_path / "zz-Templates" / "Weekly.md").write_text(
        "# Custom {{week}}\n\n## Project statuses\n")
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.obsidian.mode = "filesystem"
    v = FilesystemVault(str(tmp_path))
    synthesis = {"projects": [{"name": "VIP", "status": "ok"}], "groups": []}
    render_weekly(v, cfg, synthesis, [], date(2026, 6, 26))
    body = v.read("zz-Sherry_Weekly/2026-06-26-week-overview.md")
    assert body.startswith("# Custom 2026-06-26")  # vault template won over packaged default


def test_load_default_weekly_template_has_expected_headings() -> None:
    template = load_default_weekly_template()
    assert "{{week}}" in template
    assert "## Snapshot (frozen)" in template and "## Project statuses" in template
    assert "#weekly-planner" in template  # ties into sheet-provenance tagging


def test_update_project_section_creates_and_prepends() -> None:
    content = "# A5\n## Summary\n\n## TODO\n- [ ] x\n"
    out = update_project_section(content, "Status", "made progress", date(2026, 6, 26))
    assert "## Status" in out
    assert "- 2026-06-26 — made progress" in out
    assert out.index("## Status") < out.index("## TODO")


def test_update_project_section_ignores_heading_prefix_collision() -> None:
    content = "# P\n## Status updates\n- noise\n## TODO\n"
    out = update_project_section(content, "Status", "real", date(2026, 6, 26))
    assert "## Status\n- 2026-06-26 — real" in out  # real exact-match section created
    assert "## Status updates\n- noise" in out  # prefix-collision heading untouched


def test_build_weekly_body_skips_project_without_name() -> None:
    synthesis = {"projects": [{"status": "orphan"}, {"name": "VIP", "status": "ok"}], "groups": []}
    body = build_weekly_body(synthesis, date(2026, 6, 26))  # no KeyError
    assert "VIP" in body and "orphan" not in body


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
