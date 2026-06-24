"""Render the weekly overview and update project ## Status / ## Timeline."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from planner.collectors.vault import Project
from planner.config import Config
from planner.errors import VaultIOError, priority_emoji, priority_rank
from planner.obsidian import Vault
from planner.render_tasks import week_end, week_start

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


def _project_section(name: str, info: dict, tasks: list[dict], *, linked: bool = True) -> list[str]:
    """Render one project's frozen section: header, status/timeline, then '- TODO' bullets.

    Tasks are emitted as plain '- TODO' bullets (never '- [ ]') so they don't duplicate
    the live Dataview/Tasks queries with extra trackable checkboxes.

    Args:
        name: Project name (matches its 00-InProgress folder).
        info: The synthesis project entry, supplying optional status/timeline.
        tasks: The project's open tasks, ordered before rendering.
        linked: When True, link the header to the project note; else a plain heading.

    Returns:
        The section's markdown lines, with a trailing blank-line separator.
    """
    lines = [f"### [[00-{name}|{name}]]" if linked else f"### {name}"]
    if str(info.get("status", "")).strip():
        lines.append(f"- **Status:** {info['status']}")
    if str(info.get("timeline_assessment", "")).strip():
        lines.append(f"- **Timeline:** {info['timeline_assessment']}")
    for task in _ordered_tasks(tasks):
        emoji = priority_emoji(task.get("priority", ""))
        lines.append(f"- TODO {task.get('text', '').strip()} {emoji}".rstrip())
    lines.append("")
    return lines


def _open_tasks_block(synthesis: dict, project_names: list[str] | None = None) -> str:
    """Build the frozen per-project block, grouped by 00-InProgress folders.

    Every project in *project_names* gets a section (even with no tasks, so its
    status/timeline summary still shows); tasks whose group matches no folder
    project collect under a trailing '### Unsorted'.

    Args:
        synthesis: Synthesis dict with projects (statuses) and groups (tasks).
        project_names: Folder project names in display order; defaults to the
            named projects in the synthesis when not supplied.

    Returns:
        The frozen open-tasks-by-project markdown block.
    """
    status_by_name = {p["name"]: p for p in synthesis.get("projects", []) if p.get("name")}
    tasks_by_name: dict[str, list] = {}
    for group in synthesis.get("groups", []):
        tasks_by_name.setdefault(group.get("project", "Unsorted"), []).extend(group.get("tasks", []))
    names = project_names if project_names is not None else list(status_by_name)
    known = set(names)
    lines: list[str] = []
    for name in names:
        lines += _project_section(name, status_by_name.get(name, {}), tasks_by_name.get(name, []))
    unsorted = [task for proj, tasks in tasks_by_name.items() if proj not in known for task in tasks]
    if unsorted:
        lines += _project_section("Unsorted", {}, unsorted, linked=False)
    return "\n".join(lines).rstrip()


def _learnings_block(synthesis: dict) -> str:
    """Build the frozen learnings & follow-ups list, linking each to its source section.

    Each learning links to the parent `## header` it came from (`[[note#header]]`)
    when the synthesis supplies one, falling back to the note (`[[note]]`), or no
    link when the source is blank.
    """
    lines: list[str] = []
    for item in synthesis.get("learnings", []):
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        source = str(item.get("source", "")).strip()
        header = str(item.get("header", "")).strip()
        if source:
            target = f"{source}#{header}" if header else source
            lines.append(f"- {text} ([[{target}]])")
        else:
            lines.append(f"- {text}")
    return "\n".join(lines)


def _inject_section(text: str, heading: str, block: str) -> str:
    """Insert *block* directly under the '## heading' line, appending the section if absent."""
    if not block:
        return text
    match = re.search(rf"^## {re.escape(heading)}[ \t]*$", text, re.MULTILINE)
    if match is None:
        sep = "" if text.endswith("\n") else "\n"
        return f"{text}{sep}\n## {heading}\n{block}\n"
    return f"{text[:match.end()]}\n{block}{text[match.end():]}"


def build_weekly_body(synthesis: dict, gen_day: date, template: str | None = None,
                      project_names: list[str] | None = None) -> str:
    """Fill the weekly skeleton: replace week tokens and inject the frozen blocks.

    Args:
        synthesis: Synthesis dict with projects, groups, highlights, learnings.
        gen_day: The date the weekly overview is generated for.
        template: The skeleton to fill; defaults to the packaged template.
        project_names: 00-InProgress folder names that drive the open-tasks grouping;
            defaults to the synthesis's named projects when not supplied.

    Returns:
        The complete weekly note body, regenerated deterministically each run.
    """
    skeleton = template if template is not None else load_default_weekly_template()
    body = skeleton.replace(_WEEK_TOKEN, gen_day.isoformat())
    body = body.replace("{{week_start}}", week_start(gen_day).isoformat())
    body = body.replace("{{week_end}}", week_end(gen_day).isoformat())
    body = _inject_section(body, "Highlights", _highlights_block(synthesis))
    body = _inject_section(body, "Open tasks by project", _open_tasks_block(synthesis, project_names))
    body = _inject_section(body, "Learnings & Follow-ups", _learnings_block(synthesis))
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
    project_names = [p.name for p in projects]
    vault.write(weekly_path, build_weekly_body(synthesis, gen_day, template, project_names))
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
