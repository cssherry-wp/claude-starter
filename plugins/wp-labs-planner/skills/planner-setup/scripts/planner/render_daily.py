"""Render the daily note: ensure it exists, inject sections under ## Notes."""
from __future__ import annotations

from datetime import date

from planner.config import Config
from planner.obsidian import Vault


_PROJECT_TAG_PREFIX = "#project/"


def _header_project(project: str) -> str:
    """Render an event header's project as a clickable note link, or pass it through.

    A '#project/<Name>' tag becomes '[[00-<Name>|<Name>]]' (linking the project note);
    any other or empty value is returned unchanged so non-project text still shows.
    """
    if project.startswith(_PROJECT_TAG_PREFIX):
        name = project[len(_PROJECT_TAG_PREFIX):]
        return f"[[00-{name}|{name}]]"
    return project


def _join_link(url: str) -> str:
    """Return a '- [Join <Provider>](url)' bullet for a Zoom/Teams URL, or '' if none."""
    if not url:
        return ""
    lowered = url.lower()
    label = "Zoom" if "zoom" in lowered else "Teams" if "teams" in lowered else "call"
    return f"- [Join {label}]({url})"


def build_notes_block(synthesis: dict) -> str:
    """Assemble the Markdown injected under the daily note's ## Notes heading."""
    parts: list[str] = []
    for call in synthesis.get("calls", []):
        title = call.get("title", "Event")
        parts.append(f"### {title} {_header_project(call.get('project', ''))}".rstrip())
        join = _join_link(call.get("video_url", "").strip())
        if join:
            parts.append(join)
        time = call.get("time", "").strip()
        if time:
            parts.append(f"- {time} {call.get('project', '')}".rstrip())
        people = call.get("people") or []
        if people:
            parts.append(f"#### People for {title}")
            parts.extend(f"- {tag}" for tag in people)
        summary = call.get("previous_summary", "").strip()
        if summary:
            parts.append(f"#### Relevant previous summary for {title}")
            parts.append(f"- {summary}")
    acc = synthesis.get("accomplishments_md", "").strip()
    if acc:
        parts.append("### ✅ This Week So Far")
        parts.append(acc)
    learn = synthesis.get("learnings_md", "").strip()
    if learn:
        parts.append("### 📓 Learnings & Follow-ups")
        parts.append(learn)
    return "\n".join(parts)


def daily_note_path(vault: Vault, cfg: Config, today: date) -> str:
    """Return today's daily-note path (via MCP periodic path when available)."""
    getter = getattr(vault, "periodic_note_path", None)
    if getter:
        path = getter("daily")
        if path:
            return path
    return f"{cfg.vault.daily_output_dir}/{today.isoformat()}.md"


def ensure_daily_note(vault: Vault, cfg: Config, today: date) -> str:
    """Ensure today's note exists; create via Daily Notes command or a stub."""
    path = daily_note_path(vault, cfg, today)
    if vault.exists(path):
        return path
    runner = getattr(vault, "execute_command", None)
    if runner:
        runner("daily-notes")
    if not vault.exists(path):
        vault.write(path, "## Notes\n\n## TODO\n")
    return path


def render_daily(vault: Vault, cfg: Config, synthesis: dict, today: date) -> str:
    """Ensure today's note and inject the synthesized sections under ## Notes."""
    path = ensure_daily_note(vault, cfg, today)
    block = build_notes_block(synthesis)
    if block.strip():
        vault.patch_heading(path, "Notes", block, operation="append")
    return path
