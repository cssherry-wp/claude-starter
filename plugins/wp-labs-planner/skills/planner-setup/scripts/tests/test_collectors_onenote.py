from __future__ import annotations

from pathlib import Path

from planner.collectors.onenote import convert


def test_convert_success(tmp_path: Path) -> None:
    src = tmp_path / "n.one"
    src.write_text("binary-ish")
    # Converter that writes Markdown to {output}.
    cmd = "sh -c 'echo \"# Converted\" > \"$2\"' _ {input} {output}"
    md = convert(str(src), cmd)
    assert "# Converted" in md


def test_convert_failure_returns_placeholder(tmp_path: Path) -> None:
    md = convert(str(tmp_path / "missing.one"), "false {input} {output}")
    assert md.startswith("⚠️ OneNote unavailable")


def test_convert_no_output_returns_placeholder(tmp_path: Path) -> None:
    src = tmp_path / "n.one"
    src.write_text("data")
    md = convert(str(src), "true {input} {output}")  # exits 0, writes nothing
    assert md.startswith("⚠️ OneNote unavailable")
