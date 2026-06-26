"""OneNote collector: convert .one files to Markdown via a pluggable command."""
from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path


def convert(one_path: str, converter_command: str) -> str:
    """Run converter_command ({input}/{output} placeholders); return Markdown.

    Never raises: on any failure returns a placeholder string so the run continues.

    Args:
        one_path: Path to the OneNote file.
        converter_command: Command with {input} and {output} placeholders.

    Returns:
        Markdown content from the converter, or a placeholder on failure.
    """
    if not converter_command or not Path(one_path).is_file():
        return f"⚠️ OneNote unavailable: {one_path}"
    with tempfile.TemporaryDirectory() as tmp:
        out_path = str(Path(tmp) / "out.md")
        cmd = converter_command.replace("{input}", shlex.quote(one_path)).replace("{output}", shlex.quote(out_path))
        try:
            subprocess.run(shlex.split(cmd), capture_output=True, timeout=120, check=True)
            return Path(out_path).read_text(encoding="utf-8")
        except (subprocess.SubprocessError, OSError):
            return f"⚠️ OneNote unavailable: {one_path}"
