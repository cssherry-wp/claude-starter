from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from planner.collectors.vault import list_projects, open_tasks, recent_notes
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


def test_open_tasks_ignores_fenced_code_blocks(tmp_path: Path) -> None:
    proj = tmp_path / "00-InProgress" / "A5"
    proj.mkdir(parents=True)
    (proj / "00-A5.md").write_text(
        "# A5\n## TODO\n- [ ] real task\n```md\n- [ ] code-block example\n```\n")
    tasks = open_tasks(FilesystemVault(str(tmp_path)), cfg_for(tmp_path))
    texts = [t.text for t in tasks]
    assert any("real task" in t for t in texts)
    assert not any("code-block example" in t for t in texts)


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
