"""Render the weekly overview and update project ## Status / ## Timeline."""
from __future__ import annotations

import re
from datetime import date

from planner.collectors.vault import Project
from planner.config import Config
from planner.errors import priority_emoji, priority_rank
from planner.obsidian import Vault

WEEKLY_DATAVIEW = (
    "```dataview\n"
    "TASK\n"
    'FROM -"zz-Templates"\n'
    'WHERE !completed AND contains(string(tags), "#project/")\n'
    "GROUP BY filter(tags, (t) => startswith(t, \"#project/\"))[0] AS Project\n"
    "```\n"
)


def _ordered_tasks(tasks: list[dict]) -> list[dict]:
    return sorted(tasks, key=lambda t: priority_rank(t.get("priority", "")))


def build_weekly_body(synthesis: dict, gen_day: date) -> str:
    """Build the weekly note: frontmatter, live Dataview, then static snapshot.

    Args:
        synthesis: Synthesis dict containing projects and groups with tasks.
        gen_day: The date for which the weekly overview is generated.

    Returns:
        The complete weekly note body with frontmatter, dataview, and snapshot.
    """
    lines = ["---", "tags:", "- Weekly", "---", "",
             f"# Week overview — {gen_day.isoformat()}", "", WEEKLY_DATAVIEW,
             "## Snapshot (frozen)", ""]
    for group in synthesis.get("groups", []):
        name = group.get("project", "Unsorted")
        lines.append(f"### [[00-{name}|{name}]]")
        for task in _ordered_tasks(group.get("tasks", [])):
            emoji = priority_emoji(task.get("priority", ""))
            lines.append(f"- [ ] {task.get('text', '').strip()} {emoji}".rstrip())
        lines.append("")
    statuses = [p for p in synthesis.get("projects", []) if p.get("name")]
    if statuses:
        lines.append("## Project statuses")
        for proj in statuses:
            name = proj["name"]
            lines.append(f"- **[[00-{name}|{name}]]** — {proj.get('status', '')}")
    return "\n".join(lines) + "\n"


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
    vault.write(weekly_path, build_weekly_body(synthesis, gen_day))
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
