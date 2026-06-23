from __future__ import annotations

import subprocess
from pathlib import Path

from planner.gitcommit import commit_files, is_git_repo


def init_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@x.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True)
    return tmp_path


def test_is_git_repo(tmp_path: Path) -> None:
    assert not is_git_repo(str(tmp_path))
    init_repo(tmp_path)
    assert is_git_repo(str(tmp_path))


def test_commit_only_named_file(tmp_path: Path) -> None:
    init_repo(tmp_path)
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "b.md").write_text("b")  # must NOT be committed
    assert commit_files(str(tmp_path), ["a.md"], "planner: test")
    tracked = subprocess.run(["git", "-C", str(tmp_path), "ls-files"],
                             capture_output=True, text=True, check=True).stdout
    assert "a.md" in tracked and "b.md" not in tracked


def test_commit_no_changes_is_noop(tmp_path: Path) -> None:
    init_repo(tmp_path)
    assert commit_files(str(tmp_path), ["missing.md"], "planner: test") is False
