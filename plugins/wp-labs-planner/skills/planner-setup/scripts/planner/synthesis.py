"""LLM backend abstraction and daily/weekly synthesis."""
from __future__ import annotations

import json
import subprocess
from typing import Any

from planner.config import LlmCfg
from planner.errors import SynthesisError


def run_backend(cfg: LlmCfg, prompt: str) -> str:
    """Run the configured LLM backend on `prompt`; return its stdout text."""
    if cfg.backend == "local" and cfg.endpoint:
        return _run_http(cfg, prompt)
    cmd = [cfg.command, *cfg.flags]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=300)
    except (subprocess.SubprocessError, OSError) as exc:
        raise SynthesisError(f"LLM backend failed to run: {exc}") from exc
    if proc.returncode != 0 or not proc.stdout.strip():
        raise SynthesisError(f"LLM backend returned no output (rc={proc.returncode}): {proc.stderr[:200]}")
    return proc.stdout


def _run_http(cfg: LlmCfg, prompt: str) -> str:
    """POST to Ollama-compatible local LLM endpoint."""
    import urllib.request

    body = json.dumps({"model": cfg.model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(cfg.endpoint, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode())
    except (OSError, json.JSONDecodeError) as exc:
        raise SynthesisError(f"Local LLM endpoint failed: {exc}") from exc
    out = data.get("response", "")
    if not out.strip():
        raise SynthesisError("Local LLM endpoint returned empty response")
    return out


def extract_json(text: str) -> dict[str, Any]:
    """Return the first balanced {...} object found in `text`.

    Args:
        text: String that may contain JSON wrapped in prose.

    Returns:
        Parsed JSON object as a dict.

    Raises:
        SynthesisError: If no valid JSON object is found.
    """
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise SynthesisError("No JSON object found in LLM output")


def _synthesize(cfg: LlmCfg, template: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Fill template, call backend, parse JSON response."""
    prompt = template.replace("{payload}", json.dumps(payload, indent=2, default=str))
    return extract_json(run_backend(cfg, prompt))


def synthesize_daily(cfg: LlmCfg, prompt_template: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Produce the daily note's structured sections from collected inputs.

    Args:
        cfg: LLM configuration.
        prompt_template: Template string with {payload} placeholder.
        payload: Dict of daily data (events, accomplishments, todos, notes).

    Returns:
        Dict with "calls", "accomplishments_md", "learnings_md", "new_tasks".
    """
    return _synthesize(cfg, prompt_template, payload)


def synthesize_weekly(cfg: LlmCfg, prompt_template: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Produce the weekly project statuses and grouped-todo snapshot.

    Args:
        cfg: LLM configuration.
        prompt_template: Template string with {payload} placeholder.
        payload: Dict of weekly data (projects, tasks, activity).

    Returns:
        Dict with "projects" and "groups".
    """
    return _synthesize(cfg, prompt_template, payload)


def summarize_changes(cfg: LlmCfg, prompt_template: str, old: str, new: str) -> str:
    """Summarize what changed between two versions of a note's body.

    Args:
        cfg: LLM configuration.
        prompt_template: Template string with {old} and {new} placeholders.
        old: The previous version of the note body.
        new: The new version of the note body.

    Returns:
        Summary of substantive changes, trimmed of whitespace.

    Raises:
        SynthesisError: If the LLM backend fails.
    """
    prompt = prompt_template.replace("{old}", old).replace("{new}", new)
    return run_backend(cfg, prompt).strip()
