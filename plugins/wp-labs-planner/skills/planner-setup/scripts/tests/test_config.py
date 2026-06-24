from __future__ import annotations

from pathlib import Path

import pytest

from planner.config import load_config
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
    assert cfg.onenote.pdf == [str(Path("~/OneDrive/Notebooks/AI Value Creation.pdf").expanduser())]
    assert cfg.onenote.section_to_project["UVEX (Hexarmor)"] == "Hexarmor"
    assert cfg.onenote.import_dir == "OneNote"


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
