"""Render the weekly overview and update project ## Status / ## Timeline."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from planner.collectors.vault import Project
from planner.config import Config
from planner.errors import VaultIOError, priority_emoji, priority_rank
from planner.obsidian import Vault

_WEEK_TOKEN = "{{week}}"


def load_default_weekly_template() -> str:
    """Return the packaged weekly skeleton used when the vault has no Weekly.md."""
    return (Path(__file__).resolve().parent.parent / "templates" / "Weekly.md").read_text(
        encoding="utf-8")


def _vault_weekly_template(vault: Vault, cfg: Config) -> str | None:
    """Return the vault's customized weekly template, or None if it has none."""
    try:
        return vault.read(f"{cfg.vault.templates_dir}/Weekly.md")
    except VaultIOError:
        return None


def _ordered_tasks(tasks: list[dict]) -> list[dict]:
    return sorted(tasks, key=lambda t: priority_rank(t.get("priority", "")))


def _highlights_block(synthesis: dict) -> str:
    """Build the frozen highlights bullet list from synthesis 'highlights'."""
    return "\n".join(
        f"- {str(h).strip()}" for h in synthesis.get("highlights", []) if str(h).strip())


def _open_tasks_block(synthesis: dict) -> str:
    """Build the frozen per-project open-task block: status bullets then tasks."""
    status_by_name = {p["name"]: p for p in synthesis.get("projects", []) if p.get("name")}
    lines: list[str] = []
    for group in synthesis.get("groups", []):
        name = group.get("project", "Unsorted")
        lines.append(f"### [[00-{name}|{name}]]")
        info = status_by_name.get(name, {})
        if str(info.get("status", "")).strip():
            lines.append(f"- **Status:** {info['status']}")
        if str(info.get("timeline_assessment", "")).strip():
            lines.append(f"- **Timeline:** {info['timeline_assessment']}")
        for task in _ordered_tasks(group.get("tasks", [])):
            emoji = priority_emoji(task.get("priority", ""))
            lines.append(f"- [ ] {task.get('text', '').strip()} {emoji}".rstrip())
        lines.append("")
    return "\n".join(lines).rstrip()


def _snapshot_block(synthesis: dict) -> str:
    """Build the frozen per-project task snapshot, urgent tasks first."""
    lines: list[str] = []
    for group in synthesis.get("groups", []):
        name = group.get("project", "Unsorted")
        lines.append(f"### [[00-{name}|{name}]]")
        for task in _ordered_tasks(group.get("tasks", [])):
            emoji = priority_emoji(task.get("priority", ""))
            lines.append(f"- [ ] {task.get('text', '').strip()} {emoji}".rstrip())
        lines.append("")
    return "\n".join(lines).rstrip()


def _statuses_block(synthesis: dict) -> str:
    """Build the one-line-per-project status list (skipping nameless projects)."""
    statuses = [p for p in synthesis.get("projects", []) if p.get("name")]
    return "\n".join(
        f"- **[[00-{p['name']}|{p['name']}]]** — {p.get('status', '')}" for p in statuses)


def _inject_section(text: str, heading: str, block: str) -> str:
    """Insert *block* directly under the '## heading' line, appending the section if absent."""
    if not block:
        return text
    match = re.search(rf"^## {re.escape(heading)}[ \t]*$", text, re.MULTILINE)
    if match is None:
        sep = "" if text.endswith("\n") else "\n"
        return f"{text}{sep}\n## {heading}\n{block}\n"
    return f"{text[:match.end()]}\n{block}{text[match.end():]}"


def build_weekly_body(synthesis: dict, gen_day: date, template: str | None = None) -> str:
    """Fill the weekly template skeleton with the snapshot and project statuses.

    Args:
        synthesis: Synthesis dict containing projects and groups with tasks.
        gen_day: The date for which the weekly overview is generated.
        template: The skeleton to fill; defaults to the packaged template.

    Returns:
        The complete weekly note body, regenerated deterministically each run.
    """
    skeleton = template if template is not None else load_default_weekly_template()
    body = skeleton.replace(_WEEK_TOKEN, gen_day.isoformat())
    body = _inject_section(body, "Snapshot (frozen)", _snapshot_block(synthesis))
    body = _inject_section(body, "Project statuses", _statuses_block(synthesis))
    return body if body.endswith("\n") else body + "\n"


def update_project_section(
    content: str, heading: str, dated_line: str, entry_date: date | None = None
) -> str:
    """Insert a dated bullet newest-first under ## heading (create before ## TODO).

    Args:
        content: The original content of the project note.
        heading: The section heading (without ##).
        dated_line: The line text to add (will be prefixed with date).
        entry_date: The date to stamp the bullet; defaults to today.

    Returns:
        The updated content with the dated bullet added under the heading.
    """
    stamp = (entry_date or date.today()).isoformat()
    bullet = f"- {stamp} — {dated_line}"
    match = re.search(rf"^## {re.escape(heading)}[ \t]*$", content, re.MULTILINE)
    if match:
        idx = match.end()
        return content[:idx] + "\n" + bullet + content[idx:]
    todo = re.search(r"^## TODO[ \t]*$", content, re.MULTILINE)
    insert_at = todo.start() if todo else len(content)
    block = f"## {heading}\n{bullet}\n\n"
    return content[:insert_at] + block + content[insert_at:]


def render_weekly(vault: Vault, cfg: Config, synthesis: dict,
                  projects: list[Project], gen_day: date) -> list[str]:
    """Write the weekly overview and update each project note. Returns touched paths.

    Args:
        vault: The vault to read from and write to.
        cfg: Configuration containing weekly_output_dir path.
        synthesis: Synthesis dict with projects and groups.
        projects: List of Project objects to update.
        gen_day: The date for which the weekly overview is generated.

    Returns:
        List of touched file paths (weekly overview + updated projects).
    """
    touched: list[str] = []
    weekly_path = f"{cfg.vault.weekly_output_dir}/{gen_day.isoformat()}-week-overview.md"
    template = _vault_weekly_template(vault, cfg) or load_default_weekly_template()
    vault.write(weekly_path, build_weekly_body(synthesis, gen_day, template))
    touched.append(weekly_path)
    status_by_name = {p["name"]: p for p in synthesis.get("projects", []) if p.get("name")}
    for proj in projects:
        info = status_by_name.get(proj.name)
        if not info:
            continue
        content = vault.read(proj.path)
        content = update_project_section(content, "Status", info.get("status", ""), gen_day)
        content = update_project_section(content, "Timeline", info.get("timeline_assessment", ""), gen_day)
        vault.write(proj.path, content)
        touched.append(proj.path)
    return touched
