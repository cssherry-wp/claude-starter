"""Load and validate config.yaml into typed dataclasses."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from planner.errors import ConfigError

_DOC_ID_RE = re.compile(r"/document/d/([A-Za-z0-9_-]+)")


@dataclass
class GoogleCfg:
    credentials_path: str
    token_path: str
    planner_address: str
    gdoc_id: str


@dataclass
class OneNoteCfg:
    pdf: list[str]
    section_to_project: dict[str, str]
    import_dir: str


@dataclass
class VaultCfg:
    path: str
    vault_name: str
    templates_dir: str
    projects_dir: str
    daily_output_dir: str
    weekly_output_dir: str
    todo_files: list[str]
    git_commit: bool


@dataclass
class ObsidianCfg:
    mode: str
    host: str
    port: int
    cert_path: str
    api_key_env: str


@dataclass
class LlmCfg:
    backend: str
    command: str
    flags: list[str]
    model: str
    endpoint: str


@dataclass
class Config:
    google: GoogleCfg
    onenote: OneNoteCfg
    vault: VaultCfg
    obsidian: ObsidianCfg
    llm: LlmCfg


def _expand(value: str) -> str:
    return str(Path(os.path.expanduser(value))) if value else value


def _require(data: dict[str, Any], section: str, key: str) -> Any:
    if key not in data or data[key] in (None, ""):
        raise ConfigError(f"Missing required config key: {section}.{key}")
    return data[key]


def extract_doc_id(value: str) -> str:
    """Return the doc ID from a Google Docs URL, or the value unchanged if already an ID."""
    match = _DOC_ID_RE.search(value)
    return match.group(1) if match else value.strip()


def _build_google(g: dict[str, Any]) -> GoogleCfg:
    """Validate and construct GoogleCfg from the raw google section."""
    return GoogleCfg(
        planner_address=_require(g, "google", "planner_address"),
        credentials_path=_expand(_require(g, "google", "credentials_path")),
        token_path=_expand(_require(g, "google", "token_path")),
        gdoc_id=extract_doc_id(_require(g, "google", "gdoc_id")),
    )


def _build_onenote(o: dict[str, Any]) -> OneNoteCfg:
    """Build the OneNote config (PDF ingestion)."""
    pdf = o.get("pdf", [])
    if isinstance(pdf, str):
        pdf = [pdf]
    return OneNoteCfg(
        pdf=[_expand(p) for p in pdf],
        section_to_project=dict(o.get("section_to_project", {})),
        import_dir=o.get("import_dir", "OneNote"),
    )


def _build_vault(v: dict[str, Any]) -> VaultCfg:
    """Validate and construct VaultCfg from the raw vault section."""
    return VaultCfg(
        path=_expand(_require(v, "vault", "path")),
        vault_name=v.get("vault_name", ""),
        templates_dir=v.get("templates_dir", "zz-Templates"),
        projects_dir=v.get("projects_dir", "00-InProgress"),
        daily_output_dir=v.get("daily_output_dir", "zz-Sherry_Daily"),
        weekly_output_dir=v.get("weekly_output_dir", "zz-Sherry_Weekly"),
        todo_files=v.get("todo_files", []),
        git_commit=bool(v.get("git_commit", True)),
    )


def _build_obsidian(ob: dict[str, Any]) -> ObsidianCfg:
    """Validate and construct ObsidianCfg from the raw obsidian section."""
    cfg = ObsidianCfg(
        mode=ob.get("mode", "mcp"),
        host=ob.get("host", "127.0.0.1"),
        port=int(ob.get("port", 27124)),
        cert_path=_expand(ob.get("cert_path", "")),
        api_key_env=ob.get("api_key_env", "OBSIDIAN_API_KEY"),
    )
    if cfg.mode not in ("mcp", "filesystem"):
        raise ConfigError("obsidian.mode must be 'mcp' or 'filesystem'")
    return cfg


def _build_llm(ll: dict[str, Any]) -> LlmCfg:
    """Validate and construct LlmCfg from the raw llm section."""
    cfg = LlmCfg(
        backend=ll.get("backend", "claude"),
        command=ll.get("command", "claude"),
        flags=list(ll.get("flags", ["-p"])),
        model=ll.get("model", ""),
        endpoint=ll.get("endpoint", ""),
    )
    if cfg.backend not in ("claude", "local"):
        raise ConfigError("llm.backend must be 'claude' or 'local'")
    return cfg


def load_config(path: str) -> Config:
    """Parse config.yaml, apply defaults, and validate. Raises ConfigError."""
    p = Path(os.path.expanduser(path))
    if not p.is_file():
        raise ConfigError(f"Config file not found: {path}")
    raw = yaml.safe_load(p.read_text()) or {}
    g, o = raw.get("google", {}), raw.get("onenote", {})
    v, ob, ll = raw.get("vault", {}), raw.get("obsidian", {}), raw.get("llm", {})
    return Config(
        google=_build_google(g),
        onenote=_build_onenote(o),
        vault=_build_vault(v),
        obsidian=_build_obsidian(ob),
        llm=_build_llm(ll),
    )
