"""Collect projects, recent notes, and open tasks from the vault."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import date, timedelta

from planner.config import Config
from planner.obsidian import Vault


@dataclass
class Project:
    """A project with its metadata and content."""

    name: str
    path: str
    content: str


@dataclass
class RecentNote:
    """A recently modified note with metadata."""

    path: str
    mtime: float
    content: str


@dataclass
class OpenTask:
    """An unchecked task from a note."""

    text: str
    source_path: str
    heading: str


def list_projects(vault: Vault, cfg: Config) -> list[Project]:
    """Return one Project per `projects_dir/<Name>/00-<Name>.md`.

    Args:
        vault: The vault to read from.
        cfg: Configuration containing projects_dir path.

    Returns:
        List of Project objects found in the projects directory.
    """
    projects: list[Project] = []
    for entry in vault.list_dir(cfg.vault.projects_dir):
        if not entry.endswith("/"):
            continue
        name = entry.rstrip("/")
        path = f"{cfg.vault.projects_dir}/{name}/00-{name}.md"
        if vault.exists(path):
            projects.append(
                Project(name=name, path=path, content=vault.read(path))
            )
    return projects


def _iter_markdown(vault: Vault, cfg: Config, dirpath: str) -> list[str]:
    """Recursively list markdown file paths under dirpath, skipping templates_dir.

    Args:
        vault: The vault to read from.
        cfg: Configuration containing templates_dir name.
        dirpath: The directory path to scan.

    Returns:
        List of markdown file paths.
    """
    out: list[str] = []
    for entry in vault.list_dir(dirpath):
        rel = f"{dirpath}/{entry.rstrip('/')}"
        if entry.endswith("/"):
            if entry.rstrip("/") == cfg.vault.templates_dir:
                continue
            out.extend(_iter_markdown(vault, cfg, rel))
        elif entry.endswith(".md"):
            out.append(rel)
    return out


def open_tasks(vault: Vault, cfg: Config) -> list[OpenTask]:
    """Scan project notes for unchecked `- [ ]` tasks, excluding templates.

    Args:
        vault: The vault to read from.
        cfg: Configuration containing projects_dir.

    Returns:
        List of OpenTask objects found in project notes.
    """
    tasks: list[OpenTask] = []
    for proj in list_projects(vault, cfg):
        heading = ""
        for line in proj.content.splitlines():
            if line.startswith("## "):
                heading = line[3:].strip()
            elif line.lstrip().startswith("- [ ]"):
                tasks.append(
                    OpenTask(
                        text=line.strip()[5:].strip(),
                        source_path=proj.path,
                        heading=heading,
                    )
                )
    return tasks


def _git_recent(repo_path: str, days: int) -> set[str]:
    """Get recently modified files from git log.

    Args:
        repo_path: Path to the git repository.
        days: Number of days to look back.

    Returns:
        Set of markdown file paths modified in the last N days.
    """
    try:
        out = subprocess.run(
            [
                "git",
                "-C",
                repo_path,
                "log",
                f"--since={days} days ago",
                "--name-only",
                "--pretty=format:",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return set()
    return {line.strip() for line in out.splitlines() if line.strip().endswith(".md")}


def recent_notes(
    vault: Vault, cfg: Config, today: date, repo_path: str | None
) -> list[RecentNote]:
    """Past-week daily notes + recently-modified notes (git-confirmed when possible).

    Args:
        vault: The vault to read from.
        cfg: Configuration containing daily_output_dir.
        today: The current date, used to compute the past 7 days.
        repo_path: Path to a git repository (optional).

    Returns:
        List of RecentNote objects for the past week and recently modified files.
    """
    paths: list[str] = []
    for delta in range(1, 8):
        d = today - timedelta(days=delta)
        p = f"{cfg.vault.daily_output_dir}/{d.isoformat()}.md"
        if vault.exists(p):
            paths.append(p)
    git_paths = _git_recent(repo_path, days=2) if repo_path else set()
    for gp in git_paths:
        if gp.endswith(".md") and vault.exists(gp) and gp not in paths:
            paths.append(gp)
    notes: list[RecentNote] = []
    for p in paths:
        notes.append(
            RecentNote(path=p, mtime=vault.stat_mtime(p), content=vault.read(p))
        )
    return notes
