"""Render the daily note: ensure it exists, inject sections under ## Notes."""
from __future__ import annotations

from datetime import date

from planner.config import Config
from planner.errors import priority_emoji
from planner.obsidian import Vault


def build_notes_block(synthesis: dict) -> str:
    """Assemble the Markdown injected under the daily note's ## Notes heading."""
    parts: list[str] = []
    for call in synthesis.get("calls", []):
        title = call.get("title", "Event")
        project = call.get("project", "")
        parts.append(f"### {title} {project}".rstrip())
        time = call.get("time", "").strip()
        if time:
            parts.append(f"- {time}")
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
    for task in synthesis.get("new_tasks", []):
        emoji = priority_emoji(task.get("priority", ""))
        parts.append(f"- [ ] {task.get('text', '').strip()} {emoji}".rstrip())
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
