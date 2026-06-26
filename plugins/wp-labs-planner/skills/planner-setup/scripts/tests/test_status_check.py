from __future__ import annotations

from pathlib import Path

import status_check  # noqa: E402 — sibling script, see conftest path insert

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def test_check_reports_flags(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("OBSIDIAN_API_KEY", raising=False)
    flags = status_check.check(str(FIXTURE))
    assert flags["config_present"] is True
    assert flags["config_valid"] is True
    assert flags["obsidian_env_set"] is False


def test_check_missing_config(tmp_path) -> None:
    flags = status_check.check(str(tmp_path / "nope.yaml"))
    assert flags["config_present"] is False
    assert flags["config_valid"] is False
