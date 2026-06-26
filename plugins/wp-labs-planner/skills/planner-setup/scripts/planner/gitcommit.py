"""Best-effort git commit of only the files a planner run touched."""
from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)


def is_git_repo(path: str) -> bool:
    """Return True if `path` is inside a git work tree.

    Args:
        path: Path to check for git work tree.

    Returns:
        True if path is inside a git work tree, False otherwise.
    """
    try:
        res = subprocess.run(["git", "-C", path, "rev-parse", "--is-inside-work-tree"],
                             capture_output=True, text=True, timeout=10)
        return res.returncode == 0 and res.stdout.strip() == "true"
    except (subprocess.SubprocessError, OSError):
        return False


def commit_files(repo_path: str, files: list[str], message: str) -> bool:
    """Stage only `files` and commit. Returns True on commit, False on no-op/failure.

    Args:
        repo_path: Path to the git repository.
        files: List of file paths to stage and commit.
        message: Commit message.

    Returns:
        True if files were successfully committed, False if no-op (empty files list,
        no staged changes) or if an error occurs (never raises).
    """
    if not files:
        return False
    try:
        subprocess.run(["git", "-C", repo_path, "add", "--", *files],
                       capture_output=True, text=True, timeout=15, check=True)
        staged = subprocess.run(["git", "-C", repo_path, "diff", "--cached", "--name-only"],
                                capture_output=True, text=True, timeout=15, check=True)
        if not staged.stdout.strip():
            return False
        subprocess.run(["git", "-C", repo_path, "commit", "-m", message],
                       capture_output=True, text=True, timeout=15, check=True)
        return True
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("planner git commit skipped: %s", exc)
        return False
