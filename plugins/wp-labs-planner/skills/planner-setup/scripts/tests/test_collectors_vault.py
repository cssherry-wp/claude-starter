from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from planner.collectors.vault import attribute_material, list_projects, open_tasks, recent_notes
from planner.config import Config, load_config
from planner.obsidian import FilesystemVault

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def build_vault(tmp_path: Path) -> FilesystemVault:
    proj = tmp_path / "00-InProgress" / "A5"
    proj.mkdir(parents=True)
    (proj / "00-A5.md").write_text("# A5\n## Status\n## Timeline\n## TODO\n- [ ] do a thing 🔼\n")
    daily = tmp_path / "zz-Sherry_Daily"
    daily.mkdir()
    (daily / "2026-06-22.md").write_text("## Notes\n- yesterday\n")
    tmpl = tmp_path / "zz-Templates"
    tmpl.mkdir()
    (tmpl / "Daily.md").write_text("- [ ] template task should be ignored\n")
    return FilesystemVault(str(tmp_path))


def cfg_for(tmp_path: Path) -> Config:
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    return cfg


def _make_hexarmor(tmp_path: Path) -> None:
    """Create Hexarmor project index so list_projects returns it (valid filter)."""
    proj = tmp_path / "00-InProgress" / "Hexarmor"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "00-Hexarmor.md").write_text("# Hexarmor\n")


def test_list_projects(tmp_path: Path) -> None:
    v = build_vault(tmp_path)
    projects = list_projects(v, cfg_for(tmp_path))
    assert [p.name for p in projects] == ["A5"]
    assert "# A5" in projects[0].content


def test_open_tasks_excludes_templates(tmp_path: Path) -> None:
    v = build_vault(tmp_path)
    tasks = open_tasks(v, cfg_for(tmp_path))
    texts = [t.text for t in tasks]
    assert any("do a thing" in t for t in texts)
    assert not any("ignored" in t for t in texts)


def test_recent_notes_includes_yesterday(tmp_path: Path) -> None:
    v = build_vault(tmp_path)
    notes = recent_notes(v, cfg_for(tmp_path), date(2026, 6, 23), repo_path=None)
    assert any(n.path.endswith("2026-06-22.md") for n in notes)


def test_recent_notes_includes_recently_modified_no_git(tmp_path: Path) -> None:
    v = build_vault(tmp_path)
    cfg = cfg_for(tmp_path)
    inbox = tmp_path / "00-Inbox"
    inbox.mkdir(exist_ok=True)
    note = inbox / "x.md"
    note.write_text("# Recent\n")
    os.utime(note, None)  # set mtime to now
    notes = recent_notes(v, cfg, date.today(), repo_path=None)
    assert any("00-Inbox/x.md" in n.path for n in notes)


def test_recent_notes_nonexistent_repo_does_not_raise(tmp_path: Path) -> None:
    v = build_vault(tmp_path)
    result = recent_notes(v, cfg_for(tmp_path), date(2026, 6, 23), repo_path="/nonexistent/repo")
    assert isinstance(result, list)


def test_attribute_material_by_tag_and_folder(tmp_path: Path) -> None:
    v = build_vault(tmp_path)  # existing helper: makes 00-InProgress/A5 + a daily note
    _make_hexarmor(tmp_path)
    # A daily note with a project-tagged section.
    daily = tmp_path / "zz-Sherry_Daily" / "2026-06-23.md"
    daily.write_text("## Notes\n### Harlo testing #project/Hexarmor\n- decided to ship\n")
    # An imported page-note inside a project folder.
    (tmp_path / "00-InProgress" / "Hexarmor" / "Page.md").write_text(
        "---\ntags:\n- 2026/06/23\n- project/Hexarmor\n---\n## Notes\nchose vendor X\n")
    cfg = cfg_for(tmp_path)
    mats = attribute_material(v, cfg, date(2026, 6, 23), repo_path=None)
    hexar = mats.get("Hexarmor", [])
    assert any("decided to ship" in m.text and m.header == "Harlo testing #project/Hexarmor"
               for m in hexar)
    assert any("chose vendor X" in m.text for m in hexar)
    assert any(m.note_path.endswith("Hexarmor/Page.md") for m in hexar)


def test_attribute_material_by_link(tmp_path: Path) -> None:
    v = build_vault(tmp_path)
    _make_hexarmor(tmp_path)
    # A daily note with a heading containing a wiki-link to the Hexarmor index.
    daily = tmp_path / "zz-Sherry_Daily" / "2026-06-23.md"
    daily.write_text("### Planning [[00-Hexarmor]]\n- reviewed timeline\n")
    cfg = cfg_for(tmp_path)
    mats = attribute_material(v, cfg, date(2026, 6, 23), repo_path=None)
    hexar = mats.get("Hexarmor", [])
    assert any("reviewed timeline" in m.text for m in hexar)


def test_attribute_material_nonexistent_project_excluded(tmp_path: Path) -> None:
    v = build_vault(tmp_path)
    # No index file for Nonexistent — list_projects will not return it.
    daily = tmp_path / "zz-Sherry_Daily" / "2026-06-23.md"
    daily.write_text("### Planning #project/Nonexistent\n- some note\n")
    cfg = cfg_for(tmp_path)
    mats = attribute_material(v, cfg, date(2026, 6, 23), repo_path=None)
    assert "Nonexistent" not in mats
