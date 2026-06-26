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
    block = _open_tasks_block(synthesis, ["VIP"])
    assert "### [[00-VIP|VIP]]" in block
    assert "- **Status:** shipped beta" in block
    assert "- **Timeline:** on track" in block
    # tasks are plain '- TODO' bullets, never duplicated as '- [ ]' checkboxes
    assert "- TODO urgent one" in block and "- [ ]" not in block
    # status bullets precede the tasks; urgent precedes low
    assert block.index("**Status:**") < block.index("urgent one")
    assert block.index("urgent one") < block.index("low one")


def test_open_tasks_block_omits_blank_status() -> None:
    synthesis = {"projects": [{"name": "VIP"}],
                 "groups": [{"project": "VIP", "tasks": [{"text": "t", "priority": "high"}]}]}
    block = _open_tasks_block(synthesis, ["VIP"])
    assert "**Status:**" not in block and "**Timeline:**" not in block
    assert "- TODO t" in block


def test_open_tasks_block_shows_all_projects_and_groups_unsorted() -> None:
    synthesis = {
        "projects": [{"name": "Quiet", "status": "steady"}],
        "groups": [{"project": "Stray", "tasks": [{"text": "orphan task", "priority": "high"}]}],
    }
    # Quiet has no tasks but is a real folder project; Stray is not a folder project.
    block = _open_tasks_block(synthesis, ["Quiet"])
    assert "### [[00-Quiet|Quiet]]" in block       # shown despite no tasks
    assert "- **Status:** steady" in block
    assert "### Unsorted" in block                 # plain header, not a vault link
    assert "[[00-Unsorted" not in block
    assert "- TODO orphan task" in block
    assert block.index("### [[00-Quiet|Quiet]]") < block.index("### Unsorted")


def test_learnings_block_links_to_source_daily() -> None:
    block = _learnings_block({"learnings": [
        {"text": "Cache cut latency", "source": "2026-06-23"},
        {"text": "Follow up with vendor", "source": ""},
        {"text": "  ", "source": "2026-06-22"},
    ]})
    assert block == "- Cache cut latency ([[2026-06-23]])\n- Follow up with vendor"


def test_learnings_block_links_to_parent_header() -> None:
    block = _learnings_block({"learnings": [
        {"text": "Cache cut latency", "source": "2026-06-23", "header": "Learnings"},
        {"text": "No header here", "source": "2026-06-22", "header": ""},
    ]})
    assert block == (
        "- Cache cut latency ([[2026-06-23#Learnings]])\n- No header here ([[2026-06-22]])")


def test_build_weekly_body_orders_urgent_first() -> None:
    synthesis = {
        "projects": [{"name": "VIP", "status": "on track", "timeline_assessment": "on track"}],
        "groups": [{"project": "VIP", "tasks": [
            {"text": "low one", "priority": "low"},
            {"text": "urgent one", "priority": "highest"},
        ]}],
    }
    body = build_weekly_body(synthesis, date(2026, 6, 24))
    assert "tags:" in body and "Weekly" in body
    assert "```dataview" in body
    assert "### [[00-VIP|VIP]]" in body
    assert "- **Status:** on track" in body
    assert body.index("urgent one") < body.index("low one")


def test_build_weekly_body_fills_tokens_and_injects_sections() -> None:
    template = (
        "# Week overview — {{week}}\n\n## Highlights\n\n## Open tasks by project\n\n"
        "## Completed this week\n```dataview\nWHERE completion >= date(\"{{week_start}}\") "
        "AND completion <= date(\"{{week_end}}\")\n```\n\n## Learnings & Follow-ups\n")
    synthesis = {
        "highlights": ["Shipped beta"],
        "projects": [{"name": "VIP", "status": "shipped"}],
        "groups": [{"project": "VIP", "tasks": [{"text": "do it", "priority": "high"}]}],
        "learnings": [{"text": "Cache helps", "source": "2026-06-23"}],
    }
    body = build_weekly_body(synthesis, date(2026, 6, 24), template)
    assert "# Week overview — 2026-06-24" in body and "{{week}}" not in body
    assert 'date("2026-06-22")' in body and 'date("2026-06-28")' in body  # Mon..Sun
    assert "{{week_start}}" not in body and "{{week_end}}" not in body
    assert "- Shipped beta" in body
    assert body.index("### [[00-VIP|VIP]]") < body.index("## Completed this week")
    assert "- Cache helps ([[2026-06-23]])" in body


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
    for heading in [
        "## Highlights",
        "## Open tasks by project",
        "## Open tasks (current)",
        "## In progress this week",
        "## Learnings & Follow-ups",
        "## References",
        "## Completed this week",
        "## Cancelled this week",
    ]:
        assert heading in template
    # week-range tokens are present for the live date-scoped queries
    assert "{{week_start}}" in template and "{{week_end}}" in template
    # removed sections are gone
    assert "## Snapshot (frozen)" not in template
    assert "## From the weekly planner" not in template
    # Completed/Cancelled sit at the bottom
    assert template.index("## References") < template.index("## Completed this week")
    assert template.index("## Completed this week") < template.index("## Cancelled this week")


def test_default_weekly_template_query_fixes() -> None:
    template = load_default_weekly_template()
    # In-progress query escapes the backslash status marker so Dataview can parse it,
    assert r'status = "/" OR status = "\\"' in template
    # and the old unescaped lone-backslash form (which broke parsing) is gone.
    assert 'status = "\\"' not in template  # i.e. status = "\" is absent
    # References surfaces both created and edited times
    assert 'file.ctime AS "Created"' in template and 'file.mtime AS "Edited"' in template


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


def test_build_weekly_body_renders_all_projects_with_summaries() -> None:
    synthesis = {
        "projects": [{"name": "Quiet", "status": "steady"}, {"name": "VIP", "status": "ok"}],
        "groups": [{"project": "VIP", "tasks": [{"text": "t", "priority": "high"}]}],
    }
    # project_names drives the grouping; both projects render even though Quiet has no tasks.
    body = build_weekly_body(synthesis, date(2026, 6, 24), project_names=["Quiet", "VIP"])
    assert "### [[00-Quiet|Quiet]]" in body and "- **Status:** steady" in body
    assert "### [[00-VIP|VIP]]" in body
    assert body.index("### [[00-Quiet|Quiet]]") < body.index("### [[00-VIP|VIP]]")


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
