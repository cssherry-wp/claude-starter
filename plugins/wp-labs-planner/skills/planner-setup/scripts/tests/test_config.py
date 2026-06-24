from __future__ import annotations

from pathlib import Path

import pytest

from planner.config import extract_doc_id, load_config
from planner.errors import ConfigError

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def test_loads_valid_config() -> None:
    cfg = load_config(str(FIXTURE))
    assert cfg.google.planner_address == "sherry+planner@example.com"
    assert cfg.google.gdoc_id == "1AbCdEfGhIjKlMnOpQrStUvWxYz"
    assert cfg.vault.projects_dir == "00-InProgress"
    assert cfg.vault.git_commit is True
    assert cfg.obsidian.mode == "mcp"
    assert cfg.obsidian.port == 27124
    assert cfg.llm.backend == "claude"
    assert cfg.llm.flags == ["-p"]


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(str(tmp_path / "nope.yaml"))


def test_missing_required_key_raises(tmp_path: Path) -> None:
    bad = tmp_path / "c.yaml"
    bad.write_text("google: {}\n")
    with pytest.raises(ConfigError, match="google.planner_address"):
        load_config(str(bad))


def test_invalid_mode_raises(tmp_path: Path) -> None:
    text = FIXTURE.read_text().replace("mode: mcp", "mode: telepathy")
    bad = tmp_path / "c.yaml"
    bad.write_text(text)
    with pytest.raises(ConfigError, match="obsidian.mode"):
        load_config(str(bad))


def test_invalid_llm_backend_raises(tmp_path: Path) -> None:
    text = FIXTURE.read_text().replace("backend: claude", "backend: telepathy")
    bad = tmp_path / "c.yaml"
    bad.write_text(text)
    with pytest.raises(ConfigError, match="llm.backend"):
        load_config(str(bad))


def test_gdoc_id_accepts_full_url(tmp_path: Path) -> None:
    url = "https://docs.google.com/document/d/1AbCdEf-gh_IJK/edit?usp=sharing"
    text = FIXTURE.read_text().replace(
        "gdoc_id: 1AbCdEfGhIjKlMnOpQrStUvWxYz", f"gdoc_id: {url}")
    cfg_file = tmp_path / "c.yaml"
    cfg_file.write_text(text)
    cfg = load_config(str(cfg_file))
    assert cfg.google.gdoc_id == "1AbCdEf-gh_IJK"


def test_gdoc_id_accepts_bare_id() -> None:
    cfg = load_config(str(FIXTURE))
    assert cfg.google.gdoc_id == "1AbCdEfGhIjKlMnOpQrStUvWxYz"


def test_extract_doc_id_handles_spreadsheet_url() -> None:
    url = "https://docs.google.com/spreadsheets/d/1bB8LVB_Y5AZ/edit?gid=23#gid=23"
    assert extract_doc_id(url) == "1bB8LVB_Y5AZ"


def test_extract_doc_id_passes_bare_id() -> None:
    assert extract_doc_id("1bB8LVB_Y5AZ") == "1bB8LVB_Y5AZ"


def test_google_cfg_tab_and_weeks_defaults(tmp_path: Path) -> None:
    cfg_file = tmp_path / "c.yaml"
    cfg_file.write_text(
        "google:\n"
        "  credentials_path: /c.json\n  token_path: /t.json\n"
        "  planner_address: a@b.com\n  gdoc_id: SHEET123\n"
        "vault:\n  path: " + str(tmp_path) + "\n"
    )
    cfg = load_config(str(cfg_file))
    assert cfg.google.overview_tab == "Overview"
    assert cfg.google.weeks_back == 4
