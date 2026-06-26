from __future__ import annotations

from pathlib import Path

import pytest

from planner.obsidian import FilesystemVault
from planner.errors import VaultIOError


def make(tmp_path: Path) -> FilesystemVault:
    (tmp_path / "00-InProgress").mkdir()
    (tmp_path / "00-InProgress" / "A5").mkdir()
    (tmp_path / "note.md").write_text("## Notes\n\n- old\n\n## TODO\n")
    return FilesystemVault(str(tmp_path))


def test_list_dir(tmp_path: Path) -> None:
    v = make(tmp_path)
    assert "A5/" in v.list_dir("00-InProgress")


def test_read_and_exists(tmp_path: Path) -> None:
    v = make(tmp_path)
    assert v.exists("note.md")
    assert "## Notes" in v.read("note.md")
    assert not v.exists("missing.md")


def test_patch_heading_append(tmp_path: Path) -> None:
    v = make(tmp_path)
    v.patch_heading("note.md", "Notes", "- new line", operation="append")
    body = v.read("note.md")
    assert "- old" in body and "- new line" in body
    assert body.index("- new line") < body.index("## TODO")


def test_read_missing_raises(tmp_path: Path) -> None:
    v = make(tmp_path)
    with pytest.raises(VaultIOError):
        v.read("missing.md")


def test_patch_heading_prepend(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("## Notes\n\n- old\n\n## TODO\n")
    v = FilesystemVault(str(tmp_path))
    v.patch_heading("note.md", "Notes", "- new", operation="prepend")
    body = v.read("note.md")
    assert "- new" in body
    assert body.index("- new") < body.index("- old")
    assert body.index("- new") < body.index("## TODO")


def test_patch_heading_last_section(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("# T\n## Notes\n- old\n")
    v = FilesystemVault(str(tmp_path))
    v.patch_heading("note.md", "Notes", "- new", operation="append")
    body = v.read("note.md")
    assert "- old" in body
    assert "- new" in body
    assert body.index("- new") > body.index("- old")


def test_patch_heading_missing_heading_raises(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("## Notes\n- something\n")
    v = FilesystemVault(str(tmp_path))
    with pytest.raises(VaultIOError):
        v.patch_heading("note.md", "Nonexistent", "- x")


def test_patch_heading_ignores_prefix_collision(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("## Notes archive\n- a\n## Notes\n- b\n")
    v = FilesystemVault(str(tmp_path))
    v.patch_heading("note.md", "Notes", "- new", operation="append")
    body = v.read("note.md")
    assert body.index("- new") > body.index("- b")  # under exact '## Notes', not the archive
    assert "## Notes archive\n- a" in body  # prefix-collision heading untouched
