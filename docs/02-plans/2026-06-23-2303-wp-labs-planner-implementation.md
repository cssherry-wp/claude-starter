# wp-labs-planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python tool that generates a daily and a weekly Obsidian note by aggregating Gmail (`+planner` alias), a Google Doc, OneNote `.one` files, and Obsidian vault state — synthesized by a pluggable LLM backend — and ship it as the `wp-labs-planner` Claude Code plugin with a `planner-setup` skill.

**Architecture:** Thin entry scripts (`daily.py`, `weekly.py`) orchestrate independently-testable collector modules and a vault-I/O abstraction (`obsidian.py`) that talks to the Obsidian Local REST API's native `/mcp/` server (HTTP, Streamable transport) or a filesystem fallback. Synthesis shells out to `claude -p` or a local model. Rendering writes Obsidian-flavored Markdown and commits the touched files to the vault's git repo.

**Tech Stack:** Python ≥3.11 (managed with `uv`), `google-api-python-client` + `google-auth-oauthlib` (Gmail/Docs), `pyyaml` (config), stdlib `urllib`/`ssl`/`subprocess` (MCP HTTP + LLM + git), `pytest`/`ruff`/`mypy` (dev).

## Global Constraints

- **Python ≥3.11**, type annotations on all signatures, Google-style docstrings on public functions/classes, functions <40 lines, `ruff` + `mypy` clean. Every module starts with `from __future__ import annotations`.
- **Minimal dependencies** (DIY over 3rd-party): only `google-api-python-client`, `google-auth-oauthlib`, `google-auth`, `pyyaml` at runtime. MCP/LLM/git use the stdlib. Lock versions in `pyproject.toml`.
- **No secrets in code or config files.** `OBSIDIAN_API_KEY` comes from the environment; Google `token.json`/`credentials.json` paths are config values and the token file is gitignored.
- **Obsidian I/O** defaults to `mcp` mode: native server `POST https://127.0.0.1:27124/mcp/`, Streamable HTTP, JSON-RPC, MCP protocol `2025-06-18`, `Authorization: Bearer <OBSIDIAN_API_KEY>`, session id from the `Mcp-Session-Id` response header. TLS uses the plugin's self-signed cert via an explicit CA file — **never disable verification globally**. `filesystem` mode is the fallback.
- **Tool names (native `/mcp/`):** `vault_list`, `vault_read`, `vault_write`, `vault_append`, `vault_patch`, `vault_get_document_map`, `periodic_note_get_path`, `search_query`, `command_execute` (others unused).
- **Priority emojis** (Tasks plugin): `🔺` highest, `⏫` high, `🔼` medium, `🔽` low, `⏬` lowest.
- **Vault conventions:** projects at `00-InProgress/<Name>/00-<Name>.md` tagged `#project/<Name>`; members `#<company>/<first_last>`; daily notes `zz-Sherry_Daily/YYYY-MM-DD.md`; weekly `<weekly_output_dir>/YYYY-MM-DD-week-overview.md`; exclude `zz-Templates` from scans.
- **Resilience:** a failing/empty source degrades to a placeholder section; the run still produces a note. LLM failure → write the raw collected material under a banner.
- **Git commit:** stage only the files the run touched (never `git add -A`); best-effort (warn, never fail the run); gated by `vault.git_commit` and a git repo.
- **Dev root:** `plugins/wp-labs-planner/skills/planner-setup/scripts/`. Python package `planner`. Tests in `…/scripts/tests/` mirroring module names. All paths below are relative to the repo root.

---

## File Structure

| Path (under `plugins/wp-labs-planner/skills/planner-setup/scripts/`) | Responsibility |
| --- | --- |
| `pyproject.toml` | Package metadata, locked deps, ruff/mypy/pytest config |
| `planner/__init__.py` | Package marker + version |
| `planner/errors.py` | Shared exception types + priority-emoji constants |
| `planner/config.py` | Load + validate `config.yaml` into typed dataclasses |
| `planner/obsidian.py` | Vault-I/O abstraction: `McpVault` (native `/mcp/`) + `FilesystemVault` |
| `planner/collectors/vault.py` | Projects, open tasks, recent notes (stat + git) |
| `planner/collectors/gmail.py` | Accomplishment emails + calendar-invite calls |
| `planner/collectors/gdoc.py` | Todos from the Google Doc |
| `planner/collectors/onenote.py` | `.one` → Markdown via pluggable converter |
| `planner/synthesis.py` | LLM backend (`claude`/`local`) + daily/weekly prompt assembly & parse |
| `planner/render_daily.py` | Ensure today's note exists; inject under `## Notes` |
| `planner/render_weekly.py` | Write weekly overview; update project `## Status`/`## Timeline` |
| `planner/gitcommit.py` | Stage touched files + commit (best-effort) |
| `planner/daily.py` | `python -m planner.daily` orchestration |
| `planner/weekly.py` | `python -m planner.weekly` orchestration |
| `templates/Daily.md`, `templates/Weekly.md` | Templater templates installed into the vault |
| `templates/prompts/{daily,weekly}_synthesis.md` | LLM prompt templates |
| `templates/config.example.yaml` | Annotated config sample |
| `templates/launchd/*.plist` | macOS scheduler examples |
| `plugins/wp-labs-planner/skills/planner-setup/SKILL.md` | Setup/status skill |
| `plugins/wp-labs-planner/skills/planner-setup/scripts/status_check.py` | Idempotent status probe used by the skill |
| `plugins/wp-labs-planner/README.md` | Setup walkthrough |

---

## Phase 1 — Skeleton, errors, config

### Task 1: Package skeleton + dev tooling

**Files:**
- Create: `plugins/wp-labs-planner/skills/planner-setup/scripts/pyproject.toml`
- Create: `plugins/wp-labs-planner/skills/planner-setup/scripts/planner/__init__.py`
- Create: `plugins/wp-labs-planner/skills/planner-setup/scripts/tests/__init__.py`
- Create: `plugins/wp-labs-planner/skills/planner-setup/scripts/tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: importable `planner` package (`planner.__version__`); a working `uv` venv + `pytest` invocation used by every later task.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "wp-labs-planner"
version = "0.1.0"
description = "Daily & weekly Obsidian planner"
requires-python = ">=3.11"
dependencies = [
  "google-api-python-client==2.149.0",
  "google-auth==2.35.0",
  "google-auth-oauthlib==1.2.1",
  "pyyaml==6.0.2",
]

[project.optional-dependencies]
dev = ["pytest==8.3.3", "ruff==0.6.9", "mypy==1.11.2", "types-PyYAML==6.0.12.20240917"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["planner*"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
disallow_untyped_defs = true
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write the package marker**

`planner/__init__.py`:
```python
"""wp-labs-planner: daily & weekly Obsidian planner."""
from __future__ import annotations

__version__ = "0.1.0"
```

Create empty `tests/__init__.py`.

- [ ] **Step 3: Write a smoke test**

`tests/test_smoke.py`:
```python
from __future__ import annotations

import planner


def test_version_present() -> None:
    assert planner.__version__ == "0.1.0"
```

- [ ] **Step 4: Create the venv and run the smoke test (expect PASS)**

```bash
cd plugins/wp-labs-planner/skills/planner-setup/scripts
uv venv --python 3.11
uv pip install -e ".[dev]"
uv run pytest tests/test_smoke.py -v
```
Expected: `1 passed`.

- [ ] **Step 5: Add a `.gitignore` for the venv + token + caches**

`plugins/wp-labs-planner/skills/planner-setup/scripts/.gitignore`:
```gitignore
.venv/
__pycache__/
*.pyc
.mypy_cache/
.pytest_cache/
token.json
config.yaml
```

- [ ] **Step 6: Commit**

```bash
git add plugins/wp-labs-planner/skills/planner-setup/scripts
git commit -m "feat(planner): python package skeleton + dev tooling"
```

---

### Task 2: Errors + priority constants

**Files:**
- Create: `plugins/wp-labs-planner/skills/planner-setup/scripts/planner/errors.py`
- Test: `…/scripts/tests/test_errors.py`

**Interfaces:**
- Produces:
  - `class ConfigError(Exception)`, `class CollectorError(Exception)`, `class SynthesisError(Exception)`, `class VaultIOError(Exception)`.
  - `PRIORITY_EMOJI: dict[str, str]` mapping `"highest"|"high"|"medium"|"low"|"lowest"` → emoji.
  - `priority_emoji(level: str) -> str` returning the emoji or `""` for unknown/`"none"`.

- [ ] **Step 1: Write the failing test**

`tests/test_errors.py`:
```python
from __future__ import annotations

import pytest

from planner.errors import ConfigError, priority_emoji


def test_priority_emoji_known_levels() -> None:
    assert priority_emoji("highest") == "🔺"
    assert priority_emoji("high") == "⏫"
    assert priority_emoji("medium") == "🔼"
    assert priority_emoji("low") == "🔽"
    assert priority_emoji("lowest") == "⏬"


def test_priority_emoji_unknown_is_empty() -> None:
    assert priority_emoji("none") == ""
    assert priority_emoji("bogus") == ""


def test_config_error_is_exception() -> None:
    with pytest.raises(ConfigError):
        raise ConfigError("bad")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_errors.py -v`
Expected: FAIL (`ModuleNotFoundError: planner.errors`).

- [ ] **Step 3: Write the implementation**

`planner/errors.py`:
```python
"""Shared exception types and priority-emoji helpers."""
from __future__ import annotations


class ConfigError(Exception):
    """Raised when config.yaml is missing or invalid."""


class CollectorError(Exception):
    """Raised when a collector cannot produce usable data."""


class SynthesisError(Exception):
    """Raised when the LLM backend fails."""


class VaultIOError(Exception):
    """Raised when a vault read/write operation fails."""


PRIORITY_EMOJI: dict[str, str] = {
    "highest": "🔺",
    "high": "⏫",
    "medium": "🔼",
    "low": "🔽",
    "lowest": "⏬",
}


def priority_emoji(level: str) -> str:
    """Return the Tasks-plugin emoji for a priority level, or "" if unknown."""
    return PRIORITY_EMOJI.get(level.strip().lower(), "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_errors.py -v`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add plugins/wp-labs-planner/skills/planner-setup/scripts/planner/errors.py plugins/wp-labs-planner/skills/planner-setup/scripts/tests/test_errors.py
git commit -m "feat(planner): shared errors + priority-emoji helper"
```

---

### Task 3: Config loader

**Files:**
- Create: `…/scripts/planner/config.py`
- Test: `…/scripts/tests/test_config.py`
- Create: `…/scripts/tests/fixtures/config_valid.yaml`

**Interfaces:**
- Consumes: `planner.errors.ConfigError`.
- Produces:
  - Dataclasses: `GoogleCfg(credentials_path, token_path, planner_address, gdoc_id)`; `OneNoteCfg(files: list[str], converter_command: str)`; `VaultCfg(path, vault_name, templates_dir, projects_dir, daily_output_dir, weekly_output_dir, todo_files: list[str], git_commit: bool)`; `ObsidianCfg(mode, host, port, cert_path, api_key_env)`; `LlmCfg(backend, command, flags: list[str], model, endpoint)`; `Config(google, onenote, vault, obsidian, llm)`.
  - `load_config(path: str) -> Config` — parses YAML, applies defaults, validates required keys, raises `ConfigError` with an actionable message.
  - `extract_doc_id(value: str) -> str` — accepts either a full Google Docs URL (`https://docs.google.com/document/d/<ID>/edit`) or a bare ID and returns the ID; applied to `google.gdoc_id` so the user can paste the link.

- [ ] **Step 1: Write the fixture**

`tests/fixtures/config_valid.yaml`:
```yaml
google:
  credentials_path: ~/.config/planner/credentials.json
  token_path: ~/.config/planner/token.json
  planner_address: sherry+planner@example.com
  gdoc_id: 1AbCdEfGhIjKlMnOpQrStUvWxYz
onenote:
  files:
    - ~/OneNote/Work.one
  converter_command: "one2md {input} {output}"
vault:
  path: ~/vault
  vault_name: szhou
  templates_dir: zz-Templates
  projects_dir: 00-InProgress
  daily_output_dir: zz-Sherry_Daily
  weekly_output_dir: zz-Sherry_Weekly
  todo_files: []
  git_commit: true
obsidian:
  mode: mcp
  host: 127.0.0.1
  port: 27124
  cert_path: ~/.config/planner/obsidian.crt
  api_key_env: OBSIDIAN_API_KEY
llm:
  backend: claude
  command: claude
  flags: ["-p"]
  model: ""
  endpoint: ""
```

- [ ] **Step 2: Write the failing test**

`tests/test_config.py`:
```python
from __future__ import annotations

from pathlib import Path

import pytest

from planner.config import load_config
from planner.errors import ConfigError

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def test_loads_valid_config() -> None:
    cfg = load_config(str(FIXTURE))
    assert cfg.google.planner_address == "sherry+planner@example.com"
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: planner.config`).

- [ ] **Step 4: Write the implementation**

`planner/config.py`:
```python
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
    files: list[str]
    converter_command: str


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


def load_config(path: str) -> Config:
    """Parse config.yaml, apply defaults, and validate. Raises ConfigError."""
    p = Path(os.path.expanduser(path))
    if not p.is_file():
        raise ConfigError(f"Config file not found: {path}")
    raw = yaml.safe_load(p.read_text()) or {}
    g, o = raw.get("google", {}), raw.get("onenote", {})
    v, ob, ll = raw.get("vault", {}), raw.get("obsidian", {}), raw.get("llm", {})

    google = GoogleCfg(
        credentials_path=_expand(_require(g, "google", "credentials_path")),
        token_path=_expand(_require(g, "google", "token_path")),
        planner_address=_require(g, "google", "planner_address"),
        gdoc_id=extract_doc_id(_require(g, "google", "gdoc_id")),
    )
    onenote = OneNoteCfg(
        files=[_expand(f) for f in o.get("files", [])],
        converter_command=o.get("converter_command", ""),
    )
    vault = VaultCfg(
        path=_expand(_require(v, "vault", "path")),
        vault_name=v.get("vault_name", ""),
        templates_dir=v.get("templates_dir", "zz-Templates"),
        projects_dir=v.get("projects_dir", "00-InProgress"),
        daily_output_dir=v.get("daily_output_dir", "zz-Sherry_Daily"),
        weekly_output_dir=v.get("weekly_output_dir", "zz-Sherry_Weekly"),
        todo_files=v.get("todo_files", []),
        git_commit=bool(v.get("git_commit", True)),
    )
    obsidian = ObsidianCfg(
        mode=ob.get("mode", "mcp"),
        host=ob.get("host", "127.0.0.1"),
        port=int(ob.get("port", 27124)),
        cert_path=_expand(ob.get("cert_path", "")),
        api_key_env=ob.get("api_key_env", "OBSIDIAN_API_KEY"),
    )
    if obsidian.mode not in ("mcp", "filesystem"):
        raise ConfigError("obsidian.mode must be 'mcp' or 'filesystem'")
    llm = LlmCfg(
        backend=ll.get("backend", "claude"),
        command=ll.get("command", "claude"),
        flags=list(ll.get("flags", ["-p"])),
        model=ll.get("model", ""),
        endpoint=ll.get("endpoint", ""),
    )
    if llm.backend not in ("claude", "local"):
        raise ConfigError("llm.backend must be 'claude' or 'local'")
    return Config(google, onenote, vault, obsidian, llm)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: `6 passed`.

- [ ] **Step 6: Commit**

```bash
git add plugins/wp-labs-planner/skills/planner-setup/scripts/planner/config.py plugins/wp-labs-planner/skills/planner-setup/scripts/tests/test_config.py plugins/wp-labs-planner/skills/planner-setup/scripts/tests/fixtures/config_valid.yaml
git commit -m "feat(planner): typed config loader with validation"
```

---

## Phase 2 — Obsidian I/O abstraction

### Task 4: `Vault` protocol + `FilesystemVault`

**Files:**
- Create: `…/scripts/planner/obsidian.py`
- Test: `…/scripts/tests/test_obsidian_fs.py`

**Interfaces:**
- Consumes: `planner.config.Config`, `planner.errors.VaultIOError`.
- Produces:
  - `class Vault(typing.Protocol)` with methods: `list_dir(self, dirpath: str) -> list[str]`; `read(self, filepath: str) -> str`; `stat_mtime(self, filepath: str) -> float`; `write(self, filepath: str, content: str) -> None`; `append(self, filepath: str, content: str) -> None`; `patch_heading(self, filepath: str, heading: str, content: str, operation: str = "append") -> None`; `exists(self, filepath: str) -> bool`.
  - `class FilesystemVault` implementing `Vault` rooted at `cfg.vault.path`.
  - `make_vault(cfg: Config) -> Vault` factory (returns `FilesystemVault` for `mode=="filesystem"`; `McpVault` added in Task 5).

- [ ] **Step 1: Write the failing test**

`tests/test_obsidian_fs.py`:
```python
from __future__ import annotations

from pathlib import Path

import pytest

from planner.obsidian import FilesystemVault
from planner.errors import VaultIOError


def make(tmp_path: Path) -> FilesystemVault:
    (tmp_path / "00-InProgress").mkdir()
    (tmp_path / "00-InProgress" / "A5").mkdir()
    (tmp_path / "note.md").write_text("## Notes\n\n- old\n\n## TODO\n")
    return FilesystemVault(str(tmp_path))


def test_list_dir(tmp_path: Path) -> None:
    v = make(tmp_path)
    assert "A5/" in v.list_dir("00-InProgress")


def test_read_and_exists(tmp_path: Path) -> None:
    v = make(tmp_path)
    assert v.exists("note.md")
    assert "## Notes" in v.read("note.md")
    assert not v.exists("missing.md")


def test_patch_heading_append(tmp_path: Path) -> None:
    v = make(tmp_path)
    v.patch_heading("note.md", "Notes", "- new line", operation="append")
    body = v.read("note.md")
    assert "- old" in body and "- new line" in body
    assert body.index("- new line") < body.index("## TODO")


def test_read_missing_raises(tmp_path: Path) -> None:
    v = make(tmp_path)
    with pytest.raises(VaultIOError):
        v.read("missing.md")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_obsidian_fs.py -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Write the implementation**

`planner/obsidian.py`:
```python
"""Vault I/O abstraction: filesystem and native /mcp/ backends."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from planner.config import Config
from planner.errors import VaultIOError


class Vault(Protocol):
    """Read/write access to an Obsidian vault, backend-agnostic."""

    def list_dir(self, dirpath: str) -> list[str]: ...
    def read(self, filepath: str) -> str: ...
    def stat_mtime(self, filepath: str) -> float: ...
    def write(self, filepath: str, content: str) -> None: ...
    def append(self, filepath: str, content: str) -> None: ...
    def patch_heading(self, filepath: str, heading: str, content: str,
                      operation: str = "append") -> None: ...
    def exists(self, filepath: str) -> bool: ...


def _insert_under_heading(body: str, heading: str, content: str, operation: str) -> str:
    """Insert content relative to a `## heading` (append=end of section, prepend=start)."""
    marker = f"## {heading}"
    start = body.find(marker)
    if start == -1:
        raise VaultIOError(f"Heading '## {heading}' not found")
    after = start + len(marker)
    nxt = body.find("\n## ", after)
    section_end = len(body) if nxt == -1 else nxt
    block = ("\n" + content.strip() + "\n")
    if operation == "prepend":
        return body[:after] + block + body[after:]
    return body[:section_end].rstrip() + "\n" + block + body[section_end:]


class FilesystemVault:
    """Vault backed by direct filesystem access under a root path."""

    def __init__(self, root: str) -> None:
        self._root = Path(root)

    def _abs(self, filepath: str) -> Path:
        return self._root / filepath

    def list_dir(self, dirpath: str) -> list[str]:
        d = self._abs(dirpath)
        if not d.is_dir():
            raise VaultIOError(f"Not a directory: {dirpath}")
        return sorted(e.name + ("/" if e.is_dir() else "") for e in d.iterdir())

    def read(self, filepath: str) -> str:
        p = self._abs(filepath)
        if not p.is_file():
            raise VaultIOError(f"File not found: {filepath}")
        return p.read_text(encoding="utf-8")

    def stat_mtime(self, filepath: str) -> float:
        p = self._abs(filepath)
        if not p.is_file():
            raise VaultIOError(f"File not found: {filepath}")
        return p.stat().st_mtime

    def write(self, filepath: str, content: str) -> None:
        p = self._abs(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def append(self, filepath: str, content: str) -> None:
        existing = self.read(filepath) if self.exists(filepath) else ""
        self.write(filepath, existing + ("\n" if existing and not existing.endswith("\n") else "") + content)

    def patch_heading(self, filepath: str, heading: str, content: str,
                      operation: str = "append") -> None:
        self.write(filepath, _insert_under_heading(self.read(filepath), heading, content, operation))

    def exists(self, filepath: str) -> bool:
        return self._abs(filepath).is_file()


def make_vault(cfg: Config) -> Vault:
    """Return the configured vault backend."""
    if cfg.obsidian.mode == "filesystem":
        return FilesystemVault(cfg.vault.path)
    from planner.obsidian_mcp import McpVault  # local import to keep deps lazy

    return McpVault(cfg)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_obsidian_fs.py -v`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add plugins/wp-labs-planner/skills/planner-setup/scripts/planner/obsidian.py plugins/wp-labs-planner/skills/planner-setup/scripts/tests/test_obsidian_fs.py
git commit -m "feat(planner): Vault protocol + filesystem backend"
```

---

### Task 5: `McpVault` (native `/mcp/` HTTP client)

This adapts the JSON-RPC-over-Streamable-HTTP code validated live against the vault.

**Files:**
- Create: `…/scripts/planner/obsidian_mcp.py`
- Test: `…/scripts/tests/test_obsidian_mcp.py`

**Interfaces:**
- Consumes: `planner.config.Config`, `planner.errors.VaultIOError`.
- Produces: `class McpVault` implementing the `Vault` protocol via the native server. Internal `_call(method, params) -> dict` performs the JSON-RPC POST (parsing SSE `data:` lines) and `_tool(name, arguments) -> str` wraps `tools/call`. Maps `vault_list`/`vault_read`/`vault_write`/`vault_append`/`vault_patch`. `read` uses `vault_read`; `stat_mtime` parses the stat block from `vault_read`. Also exposes `periodic_note_path(period: str) -> str | None`, `execute_command(command_id: str) -> None`, and `search_query(query: dict) -> list`.

- [ ] **Step 1: Write the failing test (transport mocked at `_post`)**

`tests/test_obsidian_mcp.py`:
```python
from __future__ import annotations

from typing import Any

import pytest

from planner.config import load_config
from planner.errors import VaultIOError
import planner.obsidian_mcp as mcp_mod
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


class FakeTransport:
    """Stand-in for the HTTP transport: records calls, returns canned payloads."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def post(self, body: dict[str, Any], session: str | None) -> tuple[dict[str, Any], str | None]:
        self.calls.append(body)
        method = body.get("method")
        if method == "initialize":
            return {"result": {"serverInfo": {"name": "obsidian-local-rest-api"}}}, "sid-1"
        if method == "tools/call":
            name = body["params"]["name"]
            if name == "vault_list":
                return _content('["A5/","Duravant/"]'), session
            if name == "vault_read":
                return _content("## Notes\n\n- old\n\n## TODO\n"), session
            if name in ("vault_patch", "vault_write", "vault_append"):
                return _content("OK"), session
        return {"result": {}}, session


def _content(text: str) -> dict[str, Any]:
    return {"result": {"content": [{"type": "text", "text": text}]}}


@pytest.fixture
def vault(monkeypatch: pytest.MonkeyPatch) -> mcp_mod.McpVault:
    monkeypatch.setenv("OBSIDIAN_API_KEY", "test-key")
    cfg = load_config(str(FIXTURE))
    v = mcp_mod.McpVault(cfg, transport=FakeTransport())
    return v


def test_list_dir(vault: mcp_mod.McpVault) -> None:
    assert vault.list_dir("00-InProgress") == ["A5/", "Duravant/"]


def test_read(vault: mcp_mod.McpVault) -> None:
    assert "## Notes" in vault.read("note.md")


def test_patch_heading_calls_vault_patch(vault: mcp_mod.McpVault) -> None:
    vault.patch_heading("note.md", "Notes", "- x", operation="append")
    names = [c["params"]["name"] for c in vault._transport.calls if c.get("method") == "tools/call"]
    assert "vault_patch" in names


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OBSIDIAN_API_KEY", raising=False)
    cfg = load_config(str(FIXTURE))
    with pytest.raises(VaultIOError, match="OBSIDIAN_API_KEY"):
        mcp_mod.McpVault(cfg, transport=FakeTransport())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_obsidian_mcp.py -v`
Expected: FAIL (`ModuleNotFoundError: planner.obsidian_mcp`).

- [ ] **Step 3: Write the implementation**

`planner/obsidian_mcp.py`:
```python
"""Native Obsidian /mcp/ server client (Streamable HTTP, JSON-RPC)."""
from __future__ import annotations

import json
import os
import ssl
import urllib.request
from typing import Any, Protocol

from planner.config import Config
from planner.errors import VaultIOError

PROTOCOL_VERSION = "2025-06-18"


class Transport(Protocol):
    """Sends one JSON-RPC message; returns (payload, session id)."""

    def post(self, body: dict[str, Any], session: str | None) -> tuple[dict[str, Any], str | None]: ...


class HttpTransport:
    """Real Streamable-HTTP transport against the plugin's /mcp/ endpoint."""

    def __init__(self, url: str, api_key: str, cert_path: str) -> None:
        self._url = url
        self._key = api_key
        # TLS is always verified against the plugin's self-signed CA. We never
        # disable verification — require the cert so MITM on loopback is impossible.
        if not cert_path or not os.path.isfile(cert_path):
            raise VaultIOError(
                "obsidian.cert_path must point to the Local REST API certificate "
                "(download it from GET /obsidian-local-rest-api.crt). TLS verification "
                "is required; set mode: filesystem to skip the MCP entirely."
            )
        self._ctx: ssl.SSLContext = ssl.create_default_context(cafile=cert_path)
        # The plugin cert is issued for 127.0.0.1; allow IP-SAN matching only.
        self._ctx.check_hostname = True

    def post(self, body: dict[str, Any], session: str | None) -> tuple[dict[str, Any], str | None]:
        req = urllib.request.Request(self._url, method="POST", data=json.dumps(body).encode())
        req.add_header("Authorization", f"Bearer {self._key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        if session:
            req.add_header("Mcp-Session-Id", session)
            req.add_header("MCP-Protocol-Version", PROTOCOL_VERSION)
        with urllib.request.urlopen(req, context=self._ctx, timeout=30) as resp:
            sid = resp.headers.get("Mcp-Session-Id") or session
            text = resp.read().decode("utf-8")
        payload: dict[str, Any] = {}
        for line in text.splitlines():
            if line.startswith("data:"):
                payload = json.loads(line[len("data:"):].strip())
        return payload, sid


class McpVault:
    """Vault backed by the plugin's native MCP server."""

    def __init__(self, cfg: Config, transport: Transport | None = None) -> None:
        key = os.environ.get(cfg.obsidian.api_key_env, "")
        if not key:
            raise VaultIOError(f"{cfg.obsidian.api_key_env} is not set in the environment")
        url = f"https://{cfg.obsidian.host}:{cfg.obsidian.port}/mcp/"
        self._transport: Transport = transport or HttpTransport(url, key, cfg.obsidian.cert_path)
        self._session: str | None = None

    def _ensure_session(self) -> None:
        if self._session:
            return
        body = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                           "clientInfo": {"name": "wp-labs-planner", "version": "0.1.0"}}}
        payload, sid = self._transport.post(body, None)
        if not sid:
            raise VaultIOError("MCP initialize did not return a session id")
        self._session = sid

    def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._ensure_session()
        body = {"jsonrpc": "2.0", "id": 2, "method": method, "params": params}
        payload, _ = self._transport.post(body, self._session)
        if "error" in payload:
            raise VaultIOError(f"MCP {method} error: {payload['error']}")
        return payload.get("result", {})

    def _tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = self._call("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            text = "".join(c.get("text", "") for c in result.get("content", []))
            raise VaultIOError(f"{name} failed: {text}")
        return "".join(c.get("text", "") for c in result.get("content", []))

    def list_dir(self, dirpath: str) -> list[str]:
        raw = self._tool("vault_list", {"directory": dirpath})
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VaultIOError(f"vault_list returned non-JSON: {raw[:80]}") from exc
        files = data.get("files", data) if isinstance(data, dict) else data
        return list(files)

    def read(self, filepath: str) -> str:
        return self._tool("vault_read", {"path": filepath})

    def stat_mtime(self, filepath: str) -> float:
        raw = self._tool("vault_read", {"path": filepath, "includeStat": True})
        try:
            data = json.loads(raw)
            return float(data.get("stat", {}).get("mtime", 0)) / 1000.0
        except (json.JSONDecodeError, ValueError, AttributeError):
            return 0.0

    def write(self, filepath: str, content: str) -> None:
        self._tool("vault_write", {"path": filepath, "content": content})

    def append(self, filepath: str, content: str) -> None:
        self._tool("vault_append", {"path": filepath, "content": content})

    def patch_heading(self, filepath: str, heading: str, content: str,
                      operation: str = "append") -> None:
        self._tool("vault_patch", {"path": filepath, "operation": operation,
                                   "targetType": "heading", "target": heading, "content": content})

    def exists(self, filepath: str) -> bool:
        try:
            self.read(filepath)
            return True
        except VaultIOError:
            return False

    def periodic_note_path(self, period: str) -> str | None:
        try:
            raw = self._tool("periodic_note_get_path", {"period": period})
        except VaultIOError:
            return None
        try:
            return json.loads(raw).get("path")
        except json.JSONDecodeError:
            return raw.strip() or None

    def execute_command(self, command_id: str) -> None:
        self._tool("command_execute", {"commandId": command_id})

    def search_query(self, query: dict[str, Any]) -> list[Any]:
        raw = self._tool("search_query", {"query": query})
        try:
            return list(json.loads(raw))
        except json.JSONDecodeError:
            return []
```

> **Implementation note (verify on first live run):** `vault_list`/`vault_read`/`vault_patch` argument names (`directory`, `path`, `includeStat`, `targetType`) are taken from the validated tool schemas; if a live `tools/list` shows different property names, adjust here only — callers are unaffected. The earlier live test confirmed `vault_patch` with `target_type`/`operation`/`target`/`content` and `command_execute` with `commandId`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_obsidian_mcp.py -v`
Expected: `4 passed`.

- [ ] **Step 5: Live smoke check (manual, requires Obsidian running)**

```bash
# Download the plugin's self-signed cert so TLS can be verified (no -k / no CERT_NONE).
curl -sk https://127.0.0.1:27124/obsidian-local-rest-api.crt -o ~/.config/planner/obsidian.crt
OBSIDIAN_API_KEY="$OBSIDIAN_API_KEY" uv run python -c "
from planner.config import load_config; from planner.obsidian import make_vault
v = make_vault(load_config('tests/fixtures/config_valid.yaml'))
print(v.list_dir('00-InProgress'))
"
```
Expected: constructs without error (key in env + cert present) and prints the project folders. The unit tests inject a fake transport, so they never require the cert; only the real `HttpTransport` does.

- [ ] **Step 6: Commit**

```bash
git add plugins/wp-labs-planner/skills/planner-setup/scripts/planner/obsidian_mcp.py plugins/wp-labs-planner/skills/planner-setup/scripts/tests/test_obsidian_mcp.py
git commit -m "feat(planner): native /mcp/ vault backend"
```

---

## Phase 3 — Collectors

### Task 6: `vault` collector — projects, recent notes, open tasks

**Files:**
- Create: `…/scripts/planner/collectors/__init__.py` (empty)
- Create: `…/scripts/planner/collectors/vault.py`
- Test: `…/scripts/tests/test_collectors_vault.py`

**Interfaces:**
- Consumes: `planner.obsidian.Vault`, `planner.config.Config`.
- Produces:
  - `@dataclass Project(name: str, path: str, content: str)`
  - `@dataclass RecentNote(path: str, mtime: float, content: str)`
  - `@dataclass OpenTask(text: str, source_path: str, heading: str)`
  - `list_projects(vault: Vault, cfg: Config) -> list[Project]` — enumerates `projects_dir/<Name>/00-<Name>.md`.
  - `recent_notes(vault: Vault, cfg: Config, today: date, repo_path: str | None) -> list[RecentNote]` — daily notes for the past 7 days + any note whose mtime is within the last 2 days; when `repo_path` is a git repo, intersect with `git log --since="2 days ago"` changed files.
  - `open_tasks(vault: Vault, cfg: Config) -> list[OpenTask]` — scans markdown for unchecked task lines (`- [ ]`), excluding `templates_dir`.

- [ ] **Step 1: Write the failing test**

`tests/test_collectors_vault.py`:
```python
from __future__ import annotations

from datetime import date
from pathlib import Path

from planner.collectors.vault import list_projects, open_tasks, recent_notes
from planner.config import load_config
from planner.obsidian import FilesystemVault

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def build_vault(tmp_path: Path) -> FilesystemVault:
    proj = tmp_path / "00-InProgress" / "A5"
    proj.mkdir(parents=True)
    (proj / "00-A5.md").write_text("# A5\n## Status\n## Timeline\n## TODO\n- [ ] do a thing 🔼\n")
    daily = tmp_path / "zz-Sherry_Daily"
    daily.mkdir()
    (daily / "2026-06-22.md").write_text("## Notes\n- yesterday\n")
    tmpl = tmp_path / "zz-Templates"
    tmpl.mkdir()
    (tmpl / "Daily.md").write_text("- [ ] template task should be ignored\n")
    return FilesystemVault(str(tmp_path))


def cfg_for(tmp_path: Path):
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    return cfg


def test_list_projects(tmp_path: Path) -> None:
    v = build_vault(tmp_path)
    projects = list_projects(v, cfg_for(tmp_path))
    assert [p.name for p in projects] == ["A5"]
    assert "# A5" in projects[0].content


def test_open_tasks_excludes_templates(tmp_path: Path) -> None:
    v = build_vault(tmp_path)
    tasks = open_tasks(v, cfg_for(tmp_path))
    texts = [t.text for t in tasks]
    assert any("do a thing" in t for t in texts)
    assert not any("ignored" in t for t in texts)


def test_recent_notes_includes_yesterday(tmp_path: Path) -> None:
    v = build_vault(tmp_path)
    notes = recent_notes(v, cfg_for(tmp_path), date(2026, 6, 23), repo_path=None)
    assert any(n.path.endswith("2026-06-22.md") for n in notes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_collectors_vault.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the implementation**

`planner/collectors/vault.py`:
```python
"""Collect projects, recent notes, and open tasks from the vault."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from planner.config import Config
from planner.obsidian import Vault


@dataclass
class Project:
    name: str
    path: str
    content: str


@dataclass
class RecentNote:
    path: str
    mtime: float
    content: str


@dataclass
class OpenTask:
    text: str
    source_path: str
    heading: str


def list_projects(vault: Vault, cfg: Config) -> list[Project]:
    """Return one Project per `projects_dir/<Name>/00-<Name>.md`."""
    projects: list[Project] = []
    for entry in vault.list_dir(cfg.vault.projects_dir):
        if not entry.endswith("/"):
            continue
        name = entry.rstrip("/")
        path = f"{cfg.vault.projects_dir}/{name}/00-{name}.md"
        if vault.exists(path):
            projects.append(Project(name=name, path=path, content=vault.read(path)))
    return projects


def _iter_markdown(vault: Vault, cfg: Config, dirpath: str) -> list[str]:
    """Recursively list markdown file paths under dirpath, skipping templates_dir."""
    out: list[str] = []
    for entry in vault.list_dir(dirpath):
        rel = f"{dirpath}/{entry.rstrip('/')}"
        if entry.endswith("/"):
            if entry.rstrip("/") == cfg.vault.templates_dir:
                continue
            out.extend(_iter_markdown(vault, cfg, rel))
        elif entry.endswith(".md"):
            out.append(rel)
    return out


def open_tasks(vault: Vault, cfg: Config) -> list[OpenTask]:
    """Scan project notes for unchecked `- [ ]` tasks, excluding templates."""
    tasks: list[OpenTask] = []
    for proj in list_projects(vault, cfg):
        heading = ""
        for line in proj.content.splitlines():
            if line.startswith("## "):
                heading = line[3:].strip()
            elif line.lstrip().startswith("- [ ]"):
                tasks.append(OpenTask(text=line.strip()[5:].strip(),
                                      source_path=proj.path, heading=heading))
    return tasks


def _git_recent(repo_path: str, days: int) -> set[str]:
    try:
        out = subprocess.run(
            ["git", "-C", repo_path, "log", f"--since={days} days ago", "--name-only",
             "--pretty=format:"],
            capture_output=True, text=True, timeout=15, check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return set()
    return {line.strip() for line in out.splitlines() if line.strip().endswith(".md")}


def recent_notes(vault: Vault, cfg: Config, today: date,
                 repo_path: str | None) -> list[RecentNote]:
    """Past-week daily notes + recently-modified notes (git-confirmed when possible)."""
    paths: list[str] = []
    for delta in range(1, 8):
        d = today - timedelta(days=delta)
        p = f"{cfg.vault.daily_output_dir}/{d.isoformat()}.md"
        if vault.exists(p):
            paths.append(p)
    git_paths = _git_recent(repo_path, days=2) if repo_path else set()
    for gp in git_paths:
        if gp.endswith(".md") and vault.exists(gp) and gp not in paths:
            paths.append(gp)
    notes: list[RecentNote] = []
    for p in paths:
        notes.append(RecentNote(path=p, mtime=vault.stat_mtime(p), content=vault.read(p)))
    return notes
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_collectors_vault.py -v`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add plugins/wp-labs-planner/skills/planner-setup/scripts/planner/collectors plugins/wp-labs-planner/skills/planner-setup/scripts/tests/test_collectors_vault.py
git commit -m "feat(planner): vault collector (projects, tasks, recent notes)"
```

---

### Task 7: `gmail` collector

**Files:**
- Create: `…/scripts/planner/collectors/gmail.py`
- Test: `…/scripts/tests/test_collectors_gmail.py`

**Interfaces:**
- Consumes: `planner.config.GoogleCfg`; a Gmail API service object (duck-typed; injected for tests).
- Produces:
  - `@dataclass CalendarEvent(title: str, start: str, attendees: list[str], raw: str)`
  - `get_credentials(cfg: GoogleCfg, scopes: list[str]) -> Credentials` — loads `token.json`, refreshes or runs the installed-app flow against `credentials.json`. (Thin wrapper; not unit-tested — exercised in Task 14 live check.)
  - `build_gmail(creds) -> Resource` and `build_docs(creds) -> Resource` helpers.
  - `fetch_accomplishments(service, planner_address: str, since: date) -> str` — Gmail `users().messages().list(q=...)` for messages to the alias since `since`, excluding invites; returns Markdown bullets of subject + snippet.
  - `fetch_calls(service, planner_address: str) -> list[CalendarEvent]` — messages with `text/calendar` parts; parses `SUMMARY`, `DTSTART`, `ATTENDEE`. Only future-dated, timed events.
- The Gmail `q` filter: `to:<alias> after:<YYYY/MM/DD> -has:attachment OR (to:<alias> has:attachment)` — split into two helpers (`_query_tasks`, `_query_invites`) so each is testable.

- [ ] **Step 1: Write the failing test (service mocked)**

`tests/test_collectors_gmail.py`:
```python
from __future__ import annotations

from datetime import date

from planner.collectors.gmail import (
    CalendarEvent, fetch_accomplishments, fetch_calls, parse_ics,
)


class FakeMessages:
    def __init__(self, listing: dict, messages: dict) -> None:
        self._listing, self._messages = listing, messages

    def list(self, userId: str, q: str):  # noqa: N803 (Google API kwarg)
        self._last_q = q
        return _Exec(self._listing)

    def get(self, userId: str, id: str, format: str = "full"):  # noqa: N803,A002
        return _Exec(self._messages[id])


class _Exec:
    def __init__(self, value: dict) -> None:
        self._value = value

    def execute(self) -> dict:
        return self._value


class FakeService:
    def __init__(self, listing: dict, messages: dict) -> None:
        self._m = FakeMessages(listing, messages)

    def users(self):
        return self

    def messages(self):
        return self._m


def test_fetch_accomplishments_returns_markdown() -> None:
    listing = {"messages": [{"id": "m1"}]}
    messages = {"m1": {"snippet": "Shipped the thing",
                       "payload": {"headers": [{"name": "Subject", "value": "Done: shipping"}]}}}
    svc = FakeService(listing, messages)
    md = fetch_accomplishments(svc, "s+planner@x.com", date(2026, 6, 22))
    assert "Done: shipping" in md
    assert "Shipped the thing" in md


def test_parse_ics_extracts_event() -> None:
    ics = ("BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Sync with Meg\n"
           "DTSTART:20260625T150000Z\nATTENDEE;CN=Meg:mailto:meg@x.com\nEND:VEVENT\nEND:VCALENDAR")
    ev = parse_ics(ics)
    assert isinstance(ev, CalendarEvent)
    assert ev.title == "Sync with Meg"
    assert ev.start == "20260625T150000Z"
    assert "meg@x.com" in ev.attendees


def test_parse_ics_all_day_returns_none() -> None:
    ics = "BEGIN:VEVENT\nSUMMARY:Holiday\nDTSTART;VALUE=DATE:20260625\nEND:VEVENT"
    assert parse_ics(ics) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_collectors_gmail.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the implementation**

`planner/collectors/gmail.py`:
```python
"""Gmail collector: accomplishment notes and calendar-invite calls."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from planner.config import GoogleCfg

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/documents.readonly"]


@dataclass
class CalendarEvent:
    title: str
    start: str
    attendees: list[str]
    raw: str


def get_credentials(cfg: GoogleCfg, scopes: list[str]) -> Credentials:
    """Load cached credentials, refreshing or running the consent flow as needed."""
    import os

    creds: Credentials | None = None
    if os.path.exists(cfg.token_path):
        creds = Credentials.from_authorized_user_file(cfg.token_path, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cfg.credentials_path, scopes)
            creds = flow.run_local_server(port=0)
        with open(cfg.token_path, "w", encoding="utf-8") as fh:
            fh.write(creds.to_json())
    return creds


def build_gmail(creds: Credentials) -> Any:
    """Build the Gmail API client."""
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def build_docs(creds: Credentials) -> Any:
    """Build the Google Docs API client."""
    return build("docs", "v1", credentials=creds, cache_discovery=False)


def _header(message: dict[str, Any], name: str) -> str:
    for h in message.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def fetch_accomplishments(service: Any, planner_address: str, since: date) -> str:
    """Return Markdown bullets for non-invite messages to the alias since `since`."""
    q = f"to:{planner_address} after:{since.strftime('%Y/%m/%d')} -has:attachment"
    listing = service.users().messages().list(userId="me", q=q).execute()
    lines: list[str] = []
    for ref in listing.get("messages", []):
        msg = service.users().messages().get(userId="me", id=ref["id"], format="full").execute()
        subject = _header(msg, "Subject") or "(no subject)"
        snippet = msg.get("snippet", "").strip()
        lines.append(f"- **{subject}** — {snippet}")
    return "\n".join(lines)


def parse_ics(text: str) -> CalendarEvent | None:
    """Parse the first VEVENT; return None for all-day (DATE-only) events."""
    title, start, attendees = "", "", []
    for line in text.splitlines():
        if line.startswith("SUMMARY:"):
            title = line[len("SUMMARY:"):].strip()
        elif line.startswith("DTSTART;VALUE=DATE:"):
            return None
        elif line.startswith("DTSTART"):
            start = line.split(":", 1)[1].strip()
        elif line.startswith("ATTENDEE"):
            if "mailto:" in line:
                attendees.append(line.split("mailto:", 1)[1].strip())
    if not title or not start:
        return None
    return CalendarEvent(title=title, start=start, attendees=attendees, raw=text)


def _decode_part(part: dict[str, Any]) -> str:
    data = part.get("body", {}).get("data", "")
    if not data:
        return ""
    return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="replace")


def fetch_calls(service: Any, planner_address: str) -> list[CalendarEvent]:
    """Return timed calendar events from invite emails to the alias."""
    q = f"to:{planner_address} has:attachment"
    listing = service.users().messages().list(userId="me", q=q).execute()
    events: list[CalendarEvent] = []
    for ref in listing.get("messages", []):
        msg = service.users().messages().get(userId="me", id=ref["id"], format="full").execute()
        for part in msg.get("payload", {}).get("parts", []):
            if part.get("mimeType") == "text/calendar":
                ev = parse_ics(_decode_part(part))
                if ev:
                    events.append(ev)
    return events
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_collectors_gmail.py -v`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add plugins/wp-labs-planner/skills/planner-setup/scripts/planner/collectors/gmail.py plugins/wp-labs-planner/skills/planner-setup/scripts/tests/test_collectors_gmail.py
git commit -m "feat(planner): gmail collector (accomplishments + calls)"
```

---

### Task 8: `gdoc` + `onenote` collectors

**Files:**
- Create: `…/scripts/planner/collectors/gdoc.py`
- Create: `…/scripts/planner/collectors/onenote.py`
- Test: `…/scripts/tests/test_collectors_gdoc.py`
- Test: `…/scripts/tests/test_collectors_onenote.py`

**Interfaces:**
- Produces:
  - `fetch_todos(docs_service, doc_id: str) -> str` — reads the doc body and returns its plain text as Markdown.
  - `convert(one_path: str, converter_command: str) -> str` — runs `converter_command` (with `{input}`/`{output}` placeholders) and returns the resulting Markdown; on any failure returns the placeholder `"⚠️ OneNote unavailable: <path>"` (never raises).

- [ ] **Step 1: Write failing tests**

`tests/test_collectors_gdoc.py`:
```python
from __future__ import annotations

from planner.collectors.gdoc import fetch_todos


class FakeDocs:
    def __init__(self, doc: dict) -> None:
        self._doc = doc

    def documents(self):
        return self

    def get(self, documentId: str):  # noqa: N803
        return self

    def execute(self) -> dict:
        return self._doc


def test_fetch_todos_extracts_text() -> None:
    doc = {"body": {"content": [
        {"paragraph": {"elements": [{"textRun": {"content": "Email Bob\n"}}]}},
        {"paragraph": {"elements": [{"textRun": {"content": "Review PR\n"}}]}},
    ]}}
    md = fetch_todos(FakeDocs(doc), "doc-1")
    assert "Email Bob" in md and "Review PR" in md
```

`tests/test_collectors_onenote.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_collectors_gdoc.py tests/test_collectors_onenote.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `gdoc.py`**

```python
"""Google Doc collector: extract todos as plain-text Markdown."""
from __future__ import annotations

from typing import Any


def fetch_todos(docs_service: Any, doc_id: str) -> str:
    """Return the document body text (one line per paragraph) as Markdown."""
    doc = docs_service.documents().get(documentId=doc_id).execute()
    lines: list[str] = []
    for element in doc.get("body", {}).get("content", []):
        para = element.get("paragraph")
        if not para:
            continue
        text = "".join(
            run.get("textRun", {}).get("content", "")
            for run in para.get("elements", [])
        ).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)
```

- [ ] **Step 4: Write `onenote.py`**

```python
"""OneNote collector: convert .one files to Markdown via a pluggable command."""
from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path


def convert(one_path: str, converter_command: str) -> str:
    """Run converter_command ({input}/{output} placeholders); return Markdown.

    Never raises: on any failure returns a placeholder string so the run continues.
    """
    if not converter_command or not Path(one_path).is_file():
        return f"⚠️ OneNote unavailable: {one_path}"
    with tempfile.TemporaryDirectory() as tmp:
        out_path = str(Path(tmp) / "out.md")
        cmd = converter_command.replace("{input}", one_path).replace("{output}", out_path)
        try:
            subprocess.run(shlex.split(cmd), capture_output=True, timeout=120, check=True)
            return Path(out_path).read_text(encoding="utf-8")
        except (subprocess.SubprocessError, OSError):
            return f"⚠️ OneNote unavailable: {one_path}"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_collectors_gdoc.py tests/test_collectors_onenote.py -v`
Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add plugins/wp-labs-planner/skills/planner-setup/scripts/planner/collectors/gdoc.py plugins/wp-labs-planner/skills/planner-setup/scripts/planner/collectors/onenote.py plugins/wp-labs-planner/skills/planner-setup/scripts/tests/test_collectors_gdoc.py plugins/wp-labs-planner/skills/planner-setup/scripts/tests/test_collectors_onenote.py
git commit -m "feat(planner): gdoc + onenote collectors"
```

---

## Phase 4 — Synthesis

### Task 9: LLM backend + daily/weekly synthesis

**Files:**
- Create: `…/scripts/planner/synthesis.py`
- Create: `…/scripts/templates/prompts/daily_synthesis.md`
- Create: `…/scripts/templates/prompts/weekly_synthesis.md`
- Test: `…/scripts/tests/test_synthesis.py`

**Interfaces:**
- Consumes: `planner.config.LlmCfg`, `planner.errors.SynthesisError`.
- Produces:
  - `run_backend(cfg: LlmCfg, prompt: str) -> str` — `claude`: `subprocess.run([command, *flags], input=prompt)`; `local`: POST to `cfg.endpoint` (Ollama `/api/generate`) or `subprocess` `cfg.command`. Raises `SynthesisError` on non-zero/empty.
  - `synthesize_daily(cfg: LlmCfg, prompt_template: str, payload: dict) -> dict` — fills the template, calls the backend, parses JSON. Shape: `{"calls": [{"title","time","project","previous_summary"}], "accomplishments_md": str, "learnings_md": str, "new_tasks": [{"text","priority"}]}`.
  - `synthesize_weekly(cfg, prompt_template, payload) -> dict` — shape: `{"projects": [{"name","status","timeline_assessment"}], "groups": [{"project","tasks":[{"text","priority"}]}]}`.
  - `extract_json(text: str) -> dict` — pulls the first balanced `{...}` block (LLMs wrap JSON in prose); raises `SynthesisError` if none.

- [ ] **Step 1: Write the failing test (backend mocked)**

`tests/test_synthesis.py`:
```python
from __future__ import annotations

import json

import pytest

import planner.synthesis as syn
from planner.config import LlmCfg
from planner.errors import SynthesisError


def test_extract_json_from_prose() -> None:
    text = 'Sure! Here is the result:\n{"a": 1, "b": [2,3]}\nHope that helps.'
    assert syn.extract_json(text) == {"a": 1, "b": [2, 3]}


def test_extract_json_missing_raises() -> None:
    with pytest.raises(SynthesisError):
        syn.extract_json("no json here")


def test_synthesize_daily_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    canned = json.dumps({"calls": [], "accomplishments_md": "- did x",
                         "learnings_md": "", "new_tasks": [{"text": "t", "priority": "high"}]})
    monkeypatch.setattr(syn, "run_backend", lambda cfg, prompt: canned)
    cfg = LlmCfg("claude", "claude", ["-p"], "", "")
    out = syn.synthesize_daily(cfg, "PROMPT {payload}", {"x": 1})
    assert out["new_tasks"][0]["priority"] == "high"


def test_run_backend_empty_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    class P:
        returncode = 0
        stdout = "   "
        stderr = ""
    monkeypatch.setattr(syn.subprocess, "run", lambda *a, **k: P())
    with pytest.raises(SynthesisError):
        syn.run_backend(LlmCfg("claude", "claude", ["-p"], "", ""), "hi")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_synthesis.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the implementation**

`planner/synthesis.py`:
```python
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
    cmd = [cfg.command, *cfg.flags] if cfg.backend == "claude" else [cfg.command]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=300)
    except (subprocess.SubprocessError, OSError) as exc:
        raise SynthesisError(f"LLM backend failed to run: {exc}") from exc
    if proc.returncode != 0 or not proc.stdout.strip():
        raise SynthesisError(f"LLM backend returned no output (rc={proc.returncode}): {proc.stderr[:200]}")
    return proc.stdout


def _run_http(cfg: LlmCfg, prompt: str) -> str:
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
    """Return the first balanced {...} object found in `text`."""
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
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise SynthesisError("No JSON object found in LLM output")


def _synthesize(cfg: LlmCfg, template: str, payload: dict[str, Any]) -> dict[str, Any]:
    prompt = template.replace("{payload}", json.dumps(payload, indent=2, default=str))
    return extract_json(run_backend(cfg, prompt))


def synthesize_daily(cfg: LlmCfg, prompt_template: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Produce the daily note's structured sections from collected inputs."""
    return _synthesize(cfg, prompt_template, payload)


def synthesize_weekly(cfg: LlmCfg, prompt_template: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Produce the weekly project statuses and grouped-todo snapshot."""
    return _synthesize(cfg, prompt_template, payload)
```

- [ ] **Step 4: Write the prompt templates**

`templates/prompts/daily_synthesis.md`:
```markdown
You are a planning assistant. Given the JSON payload below (calendar events,
accomplishment emails, Google Doc todos, OneNote-derived notes, and recent daily
notes), produce ONLY a JSON object — no prose — with this exact shape:

{
  "calls": [
    {"title": "...", "time": "HH:MM", "project": "#project/<Name>",
     "previous_summary": "one-sentence relevant prior context or empty"}
  ],
  "accomplishments_md": "Markdown bullets summarizing what was done so far this week",
  "learnings_md": "Markdown bullets of learnings + follow-up actions from the notes",
  "new_tasks": [
    {"text": "task text", "priority": "highest|high|medium|low|lowest"}
  ]
}

Map each event to a project using #project/<Name> tags or #<company>/<first_last>
member tags in the payload. Exclude all-day events. Keep it concise.

PAYLOAD:
{payload}
```

`templates/prompts/weekly_synthesis.md`:
```markdown
You are a planning assistant. Given the JSON payload (projects with their notes,
open tasks across the vault, and this week's activity), produce ONLY a JSON object
— no prose — with this exact shape:

{
  "projects": [
    {"name": "<Name>", "status": "one-line dated status: progress + what's next",
     "timeline_assessment": "on track | slipping | blocked — brief rationale"}
  ],
  "groups": [
    {"project": "<Name>",
     "tasks": [{"text": "task text", "priority": "highest|high|medium|low|lowest"}]}
  ]
}

Group every open task under the project it belongs to (via #project/<Name>). Within
each group, order urgent tasks (highest/high) first. Keep statuses to one line.

PAYLOAD:
{payload}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_synthesis.py -v`
Expected: `4 passed`.

- [ ] **Step 6: Commit**

```bash
git add plugins/wp-labs-planner/skills/planner-setup/scripts/planner/synthesis.py plugins/wp-labs-planner/skills/planner-setup/scripts/templates/prompts plugins/wp-labs-planner/skills/planner-setup/scripts/tests/test_synthesis.py
git commit -m "feat(planner): LLM backend + daily/weekly synthesis"
```

---

## Phase 5 — Rendering

### Task 10: Daily renderer

**Files:**
- Create: `…/scripts/planner/render_daily.py`
- Test: `…/scripts/tests/test_render_daily.py`

**Interfaces:**
- Consumes: `planner.obsidian.Vault`, `planner.config.Config`, `planner.errors.priority_emoji`. For MCP mode, optionally `McpVault.execute_command`/`periodic_note_path` (accessed via `getattr`, so filesystem mode degrades gracefully).
- Produces:
  - `build_notes_block(synthesis: dict) -> str` — assembles the Markdown injected under `## Notes` (per-event `###` headers with time + `#project` + nested `#### Relevant previous summary`, then `### ✅ This Week So Far`, `### 📓 Learnings & Follow-ups`, then new tasks as `- [ ] … <emoji>`).
  - `daily_note_path(vault, cfg, today: date) -> str` — `periodic_note_path("daily")` if available, else `<daily_output_dir>/<today>.md`.
  - `ensure_daily_note(vault, cfg, today: date) -> str` — if the note is missing: in MCP mode call `execute_command("daily-notes")`; otherwise write a minimal `## Notes\n` stub. Returns the path.
  - `render_daily(vault, cfg, synthesis: dict, today: date) -> str` — ensures the note, patches `build_notes_block(...)` under `## Notes`, returns the path.

- [ ] **Step 1: Write the failing test**

`tests/test_render_daily.py`:
```python
from __future__ import annotations

from datetime import date
from pathlib import Path

from planner.config import load_config
from planner.obsidian import FilesystemVault
from planner.render_daily import build_notes_block, render_daily

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def test_build_notes_block_has_event_and_tasks() -> None:
    synthesis = {
        "calls": [{"title": "Sync", "time": "15:00", "project": "#project/VIP",
                   "previous_summary": "last sync agreed on scope"}],
        "accomplishments_md": "- shipped",
        "learnings_md": "- learned x",
        "new_tasks": [{"text": "follow up", "priority": "high"}],
    }
    block = build_notes_block(synthesis)
    assert "### Sync" in block
    assert "15:00" in block and "#project/VIP" in block
    assert "#### Relevant previous summary" in block
    assert "### ✅ This Week So Far" in block
    assert "- [ ] follow up ⏫" in block


def test_render_daily_injects(tmp_path: Path) -> None:
    daily = tmp_path / "zz-Sherry_Daily"
    daily.mkdir()
    (daily / "2026-06-23.md").write_text("## Notes\n\n## TODO\n")
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.obsidian.mode = "filesystem"
    v = FilesystemVault(str(tmp_path))
    synthesis = {"calls": [], "accomplishments_md": "- a", "learnings_md": "", "new_tasks": []}
    path = render_daily(v, cfg, synthesis, date(2026, 6, 23))
    body = v.read("zz-Sherry_Daily/2026-06-23.md")
    assert path.endswith("2026-06-23.md")
    assert "### ✅ This Week So Far" in body
    assert body.index("### ✅ This Week So Far") < body.index("## TODO")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_render_daily.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the implementation**

`planner/render_daily.py`:
```python
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
        parts.append(f"### {call.get('title', 'Event')} {call.get('project', '')}".rstrip())
        parts.append(f"- {call.get('time', '')} {call.get('project', '')}".rstrip())
        summary = call.get("previous_summary", "").strip()
        if summary:
            parts.append(f"#### Relevant previous summary for {call.get('title', 'event')}")
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_render_daily.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add plugins/wp-labs-planner/skills/planner-setup/scripts/planner/render_daily.py plugins/wp-labs-planner/skills/planner-setup/scripts/tests/test_render_daily.py
git commit -m "feat(planner): daily renderer"
```

---

### Task 11: Weekly renderer

**Files:**
- Create: `…/scripts/planner/render_weekly.py`
- Test: `…/scripts/tests/test_render_weekly.py`

**Interfaces:**
- Consumes: `planner.obsidian.Vault`, `planner.config.Config`, `planner.collectors.vault.Project`, `planner.errors.priority_emoji`.
- Produces:
  - `WEEKLY_DATAVIEW: str` — the verbatim Dataview `TASK` block grouped by `#project/<Name>` (matches `templates/Weekly.md`).
  - `build_weekly_body(synthesis: dict, gen_day: date) -> str` — frontmatter `tags: [Weekly]`, the Dataview block, then the static snapshot (grouped todos with `[[00-<Name>|<Name>]]` headers, urgent-first; per-project status lines).
  - `update_project_section(content: str, heading: str, dated_line: str) -> str` — insert `- YYYY-MM-DD — <line>` newest-first under `## heading`, creating the section before `## TODO` if absent.
  - `render_weekly(vault, cfg, synthesis: dict, projects: list[Project], gen_day: date) -> list[str]` — writes the weekly overview and updates each project's `## Status` + `## Timeline`; returns the list of touched file paths.

- [ ] **Step 1: Write the failing test**

`tests/test_render_weekly.py`:
```python
from __future__ import annotations

from datetime import date
from pathlib import Path

from planner.collectors.vault import Project
from planner.config import load_config
from planner.obsidian import FilesystemVault
from planner.render_weekly import build_weekly_body, render_weekly, update_project_section

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def test_build_weekly_body_orders_urgent_first() -> None:
    synthesis = {
        "projects": [{"name": "VIP", "status": "on track", "timeline_assessment": "on track"}],
        "groups": [{"project": "VIP", "tasks": [
            {"text": "low one", "priority": "low"},
            {"text": "urgent one", "priority": "highest"},
        ]}],
    }
    body = build_weekly_body(synthesis, date(2026, 6, 26))
    assert "tags:" in body and "Weekly" in body
    assert "```dataview" in body
    assert "[[00-VIP|VIP]]" in body
    assert body.index("urgent one") < body.index("low one")


def test_update_project_section_creates_and_prepends() -> None:
    content = "# A5\n## Summary\n\n## TODO\n- [ ] x\n"
    out = update_project_section(content, "Status", "made progress")
    assert "## Status" in out
    assert "2026" in out or "- " in out
    assert out.index("## Status") < out.index("## TODO")


def test_render_weekly_writes_and_updates(tmp_path: Path) -> None:
    proj_dir = tmp_path / "00-InProgress" / "VIP"
    proj_dir.mkdir(parents=True)
    (proj_dir / "00-VIP.md").write_text("# VIP\n## Summary\n## Timeline\n## TODO\n")
    (tmp_path / "zz-Sherry_Weekly").mkdir()
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.obsidian.mode = "filesystem"
    v = FilesystemVault(str(tmp_path))
    projects = [Project("VIP", "00-InProgress/VIP/00-VIP.md", (proj_dir / "00-VIP.md").read_text())]
    synthesis = {"projects": [{"name": "VIP", "status": "shipped", "timeline_assessment": "on track"}],
                 "groups": []}
    touched = render_weekly(v, cfg, synthesis, projects, date(2026, 6, 26))
    assert any("week-overview" in p for p in touched)
    assert "## Status" in v.read("00-InProgress/VIP/00-VIP.md")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_render_weekly.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the implementation**

`planner/render_weekly.py`:
```python
"""Render the weekly overview and update project ## Status / ## Timeline."""
from __future__ import annotations

from datetime import date

from planner.collectors.vault import Project
from planner.config import Config
from planner.errors import priority_emoji
from planner.obsidian import Vault

_PRIORITY_RANK = {"highest": 0, "high": 1, "medium": 2, "low": 3, "lowest": 4}

WEEKLY_DATAVIEW = (
    "```dataview\n"
    "TASK\n"
    'FROM -"zz-Templates"\n'
    'WHERE !completed AND contains(string(tags), "#project/")\n'
    "GROUP BY filter(tags, (t) => startswith(t, \"#project/\"))[0] AS Project\n"
    "```\n"
)


def _ordered_tasks(tasks: list[dict]) -> list[dict]:
    return sorted(tasks, key=lambda t: _PRIORITY_RANK.get(t.get("priority", "medium"), 2.5))


def build_weekly_body(synthesis: dict, gen_day: date) -> str:
    """Build the weekly note: frontmatter, live Dataview, then static snapshot."""
    lines = ["---", "tags:", "- Weekly", "---", "",
             f"# Week overview — {gen_day.isoformat()}", "", WEEKLY_DATAVIEW,
             "## Snapshot (frozen)", ""]
    for group in synthesis.get("groups", []):
        name = group.get("project", "Unsorted")
        lines.append(f"### [[00-{name}|{name}]]")
        for task in _ordered_tasks(group.get("tasks", [])):
            emoji = priority_emoji(task.get("priority", ""))
            lines.append(f"- [ ] {task.get('text', '').strip()} {emoji}".rstrip())
        lines.append("")
    statuses = synthesis.get("projects", [])
    if statuses:
        lines.append("## Project statuses")
        for proj in statuses:
            lines.append(f"- **[[00-{proj['name']}|{proj['name']}]]** — {proj.get('status', '')}")
    return "\n".join(lines) + "\n"


def update_project_section(content: str, heading: str, dated_line: str) -> str:
    """Insert a dated bullet newest-first under ## heading (create before ## TODO)."""
    from datetime import date as _date

    bullet = f"- {_date.today().isoformat()} — {dated_line}"
    marker = f"## {heading}"
    if marker in content:
        idx = content.index(marker) + len(marker)
        return content[:idx] + "\n" + bullet + content[idx:]
    todo = content.find("## TODO")
    insert_at = todo if todo != -1 else len(content)
    block = f"## {heading}\n{bullet}\n\n"
    return content[:insert_at] + block + content[insert_at:]


def render_weekly(vault: Vault, cfg: Config, synthesis: dict,
                  projects: list[Project], gen_day: date) -> list[str]:
    """Write the weekly overview and update each project note. Returns touched paths."""
    touched: list[str] = []
    weekly_path = f"{cfg.vault.weekly_output_dir}/{gen_day.isoformat()}-week-overview.md"
    vault.write(weekly_path, build_weekly_body(synthesis, gen_day))
    touched.append(weekly_path)
    status_by_name = {p["name"]: p for p in synthesis.get("projects", [])}
    for proj in projects:
        info = status_by_name.get(proj.name)
        if not info:
            continue
        content = vault.read(proj.path)
        content = update_project_section(content, "Status", info.get("status", ""))
        content = update_project_section(content, "Timeline", info.get("timeline_assessment", ""))
        vault.write(proj.path, content)
        touched.append(proj.path)
    return touched
```

`templates/Weekly.md` (installed into the vault — Templater frontmatter + the same Dataview):
```markdown
<%* const gen = tp.date.now("YYYY-MM-DD") -%>
---
tags:
- Weekly
---
# Week overview — <% gen %>

```dataview
TASK
FROM -"zz-Templates"
WHERE !completed AND contains(string(tags), "#project/")
GROUP BY filter(tags, (t) => startswith(t, "#project/"))[0] AS Project
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_render_weekly.py -v`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add plugins/wp-labs-planner/skills/planner-setup/scripts/planner/render_weekly.py plugins/wp-labs-planner/skills/planner-setup/scripts/templates/Weekly.md plugins/wp-labs-planner/skills/planner-setup/scripts/tests/test_render_weekly.py
git commit -m "feat(planner): weekly renderer + Weekly.md template"
```

---

## Phase 6 — Orchestration

### Task 12: Git commit helper

**Files:**
- Create: `…/scripts/planner/gitcommit.py`
- Test: `…/scripts/tests/test_gitcommit.py`

**Interfaces:**
- Produces:
  - `is_git_repo(path: str) -> bool`.
  - `commit_files(repo_path: str, files: list[str], message: str) -> bool` — stages only `files` (absolute or repo-relative), commits with `message`; returns True on commit, False on no-op/failure. Never raises.

- [ ] **Step 1: Write the failing test (uses a real temp git repo)**

`tests/test_gitcommit.py`:
```python
from __future__ import annotations

import subprocess
from pathlib import Path

from planner.gitcommit import commit_files, is_git_repo


def init_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@x.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "T"], check=True)
    return tmp_path


def test_is_git_repo(tmp_path: Path) -> None:
    assert not is_git_repo(str(tmp_path))
    init_repo(tmp_path)
    assert is_git_repo(str(tmp_path))


def test_commit_only_named_file(tmp_path: Path) -> None:
    init_repo(tmp_path)
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "b.md").write_text("b")  # must NOT be committed
    assert commit_files(str(tmp_path), ["a.md"], "planner: test")
    tracked = subprocess.run(["git", "-C", str(tmp_path), "ls-files"],
                             capture_output=True, text=True, check=True).stdout
    assert "a.md" in tracked and "b.md" not in tracked


def test_commit_no_changes_is_noop(tmp_path: Path) -> None:
    init_repo(tmp_path)
    assert commit_files(str(tmp_path), ["missing.md"], "planner: test") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_gitcommit.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the implementation**

`planner/gitcommit.py`:
```python
"""Best-effort git commit of only the files a planner run touched."""
from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)


def is_git_repo(path: str) -> bool:
    """Return True if `path` is inside a git work tree."""
    try:
        res = subprocess.run(["git", "-C", path, "rev-parse", "--is-inside-work-tree"],
                             capture_output=True, text=True, timeout=10)
        return res.returncode == 0 and res.stdout.strip() == "true"
    except (subprocess.SubprocessError, OSError):
        return False


def commit_files(repo_path: str, files: list[str], message: str) -> bool:
    """Stage only `files` and commit. Returns True on commit, False on no-op/failure."""
    if not files:
        return False
    try:
        subprocess.run(["git", "-C", repo_path, "add", "--", *files],
                       capture_output=True, text=True, timeout=15, check=True)
        staged = subprocess.run(["git", "-C", repo_path, "diff", "--cached", "--name-only"],
                                capture_output=True, text=True, timeout=15, check=True)
        if not staged.stdout.strip():
            return False
        subprocess.run(["git", "-C", repo_path, "commit", "-m", message],
                       capture_output=True, text=True, timeout=15, check=True)
        return True
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("planner git commit skipped: %s", exc)
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_gitcommit.py -v`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add plugins/wp-labs-planner/skills/planner-setup/scripts/planner/gitcommit.py plugins/wp-labs-planner/skills/planner-setup/scripts/tests/test_gitcommit.py
git commit -m "feat(planner): best-effort vault git-commit helper"
```

---

### Task 13: `daily.py` + `weekly.py` entry points

**Files:**
- Create: `…/scripts/planner/daily.py`
- Create: `…/scripts/planner/weekly.py`
- Test: `…/scripts/tests/test_entrypoints.py`

**Interfaces:**
- Consumes: everything above. Resolves config path from `PLANNER_CONFIG` env or `--config`.
- Produces:
  - `run_daily(cfg: Config, today: date) -> str` and `run_weekly(cfg: Config, gen_day: date) -> list[str]` — gather → synthesize → render → commit. Each collector call is wrapped so a failure becomes a placeholder (resilience), never aborting.
  - `main()` in each module: parse `--config`, load config, call the run function, print the written path(s). `python -m planner.daily` / `python -m planner.weekly`.
  - `_load_prompt(name: str) -> str` reads `templates/prompts/<name>` relative to the package.

- [ ] **Step 1: Write the failing test (collectors + synthesis + vault mocked)**

`tests/test_entrypoints.py`:
```python
from __future__ import annotations

from datetime import date
from pathlib import Path

import planner.daily as daily_mod
from planner.config import load_config
from planner.obsidian import FilesystemVault

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def test_run_daily_end_to_end(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "zz-Sherry_Daily").mkdir()
    (tmp_path / "zz-Sherry_Daily" / "2026-06-23.md").write_text("## Notes\n\n## TODO\n")
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.obsidian.mode = "filesystem"
    cfg.vault.git_commit = False

    monkeypatch.setattr(daily_mod, "make_vault", lambda c: FilesystemVault(str(tmp_path)))
    monkeypatch.setattr(daily_mod, "_gather_daily", lambda vault, cfg, today: {"x": 1})
    monkeypatch.setattr(daily_mod, "synthesize_daily",
                        lambda cfg, tmpl, payload: {"calls": [], "accomplishments_md": "- a",
                                                    "learnings_md": "", "new_tasks": []})
    path = daily_mod.run_daily(cfg, date(2026, 6, 23))
    assert path.endswith("2026-06-23.md")
    assert "### ✅ This Week So Far" in (tmp_path / "zz-Sherry_Daily" / "2026-06-23.md").read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_entrypoints.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `daily.py`**

```python
"""Entry point: build today's daily note."""
from __future__ import annotations

import argparse
import logging
import os
from datetime import date, datetime
from pathlib import Path

from planner.collectors import gdoc, gmail, onenote
from planner.collectors.vault import recent_notes
from planner.config import Config, load_config
from planner.gitcommit import commit_files, is_git_repo
from planner.obsidian import make_vault
from planner.render_daily import render_daily
from planner.synthesis import synthesize_daily

log = logging.getLogger(__name__)


def _load_prompt(name: str) -> str:
    return (Path(__file__).resolve().parent.parent / "templates" / "prompts" / name).read_text()


def _safe(label: str, fn):  # type: ignore[no-untyped-def]
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — resilience: degrade, never abort
        log.warning("daily collector '%s' failed: %s", label, exc)
        return f"⚠️ {label} unavailable"


def _gather_daily(vault, cfg: Config, today: date) -> dict:  # type: ignore[no-untyped-def]
    week_start = today.fromordinal(today.toordinal() - today.weekday())
    creds_holder: dict = {}

    def services():  # lazy: only authenticate if a Google collector runs
        if "g" not in creds_holder:
            creds = gmail.get_credentials(cfg.google, gmail.GMAIL_SCOPES)
            creds_holder["g"] = (gmail.build_gmail(creds), gmail.build_docs(creds))
        return creds_holder["g"]

    repo = cfg.vault.path if is_git_repo(cfg.vault.path) else None
    return {
        "accomplishments": _safe("gmail", lambda: gmail.fetch_accomplishments(
            services()[0], cfg.google.planner_address, week_start)),
        "calls": _safe("calls", lambda: [e.__dict__ for e in gmail.fetch_calls(
            services()[0], cfg.google.planner_address)]),
        "todos": _safe("gdoc", lambda: gdoc.fetch_todos(services()[1], cfg.google.gdoc_id)),
        "onenote": _safe("onenote", lambda: "\n\n".join(
            onenote.convert(p, cfg.onenote.converter_command) for p in cfg.onenote.files)),
        "recent_notes": _safe("recent", lambda: [n.__dict__ for n in recent_notes(
            vault, cfg, today, repo)]),
    }


def run_daily(cfg: Config, today: date) -> str:
    """Gather → synthesize → render → commit; return the daily note path."""
    vault = make_vault(cfg)
    payload = _gather_daily(vault, cfg, today)
    synthesis = synthesize_daily(cfg.llm, _load_prompt("daily_synthesis.md"), payload)
    path = render_daily(vault, cfg, synthesis, today)
    if cfg.vault.git_commit and is_git_repo(cfg.vault.path):
        commit_files(cfg.vault.path, [str(Path(cfg.vault.path) / path)],
                     f"planner: daily {today.isoformat()}")
    return path


def main() -> None:
    """CLI entry: python -m planner.daily [--config PATH]."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=os.environ.get("PLANNER_CONFIG", "config.yaml"))
    args = parser.parse_args()
    cfg = load_config(args.config)
    print(run_daily(cfg, datetime.now().date()))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write `weekly.py`**

```python
"""Entry point: build the weekly overview (run on Friday)."""
from __future__ import annotations

import argparse
import logging
import os
from datetime import date, datetime
from pathlib import Path

from planner.collectors import gdoc, gmail, onenote
from planner.collectors.vault import list_projects, open_tasks
from planner.config import Config, load_config
from planner.gitcommit import commit_files, is_git_repo
from planner.obsidian import make_vault
from planner.render_weekly import render_weekly
from planner.synthesis import synthesize_weekly

log = logging.getLogger(__name__)


def _load_prompt(name: str) -> str:
    return (Path(__file__).resolve().parent.parent / "templates" / "prompts" / name).read_text()


def _safe(label: str, fn):  # type: ignore[no-untyped-def]
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — resilience
        log.warning("weekly collector '%s' failed: %s", label, exc)
        return []


def _gather_weekly(vault, cfg: Config) -> tuple[dict, list]:  # type: ignore[no-untyped-def]
    projects = list_projects(vault, cfg)
    payload = {
        "projects": [{"name": p.name, "content": p.content} for p in projects],
        "open_tasks": [t.__dict__ for t in _safe("tasks", lambda: open_tasks(vault, cfg))],
    }
    return payload, projects


def run_weekly(cfg: Config, gen_day: date) -> list[str]:
    """Gather → synthesize → render → commit; return touched paths."""
    vault = make_vault(cfg)
    payload, projects = _gather_weekly(vault, cfg)
    synthesis = synthesize_weekly(cfg.llm, _load_prompt("weekly_synthesis.md"), payload)
    touched = render_weekly(vault, cfg, synthesis, projects, gen_day)
    if cfg.vault.git_commit and is_git_repo(cfg.vault.path):
        commit_files(cfg.vault.path, [str(Path(cfg.vault.path) / p) for p in touched],
                     f"planner: weekly overview {gen_day.isoformat()}")
    return touched


def main() -> None:
    """CLI entry: python -m planner.weekly [--config PATH]."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=os.environ.get("PLANNER_CONFIG", "config.yaml"))
    args = parser.parse_args()
    cfg = load_config(args.config)
    for path in run_weekly(cfg, datetime.now().date()):
        print(path)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test + full suite + lint + types**

```bash
uv run pytest -v
uv run ruff check planner
uv run mypy planner
```
Expected: all tests pass; ruff clean; mypy clean.

- [ ] **Step 6: Commit**

```bash
git add plugins/wp-labs-planner/skills/planner-setup/scripts/planner/daily.py plugins/wp-labs-planner/skills/planner-setup/scripts/planner/weekly.py plugins/wp-labs-planner/skills/planner-setup/scripts/tests/test_entrypoints.py
git commit -m "feat(planner): daily + weekly entry points with resilient gather"
```

**Checkpoint:** the tool is now CLI-runnable end-to-end (`python -m planner.daily`) given a `config.yaml` and a running Obsidian. Phase 7 packages it.

---

## Phase 7 — Plugin packaging, setup skill, docs

### Task 14: `config.example.yaml`, `Daily.md`, `status_check.py`

**Files:**
- Create: `…/scripts/templates/config.example.yaml`
- Create: `…/scripts/templates/Daily.md` (the user's provided template, verbatim)
- Create: `plugins/wp-labs-planner/skills/planner-setup/scripts/status_check.py`
- Test: `…/scripts/tests/test_status_check.py`

**Interfaces:**
- Produces:
  - `templates/config.example.yaml` — annotated copy of the validated config schema (Task 3 fixture + comments).
  - `templates/Daily.md` — the exact Templater daily template the user supplied.
  - `check(config_path: str) -> dict[str, bool]` in `status_check.py` — returns a dict of readiness flags: `config_present`, `config_valid`, `token_present`, `obsidian_env_set`, `vault_reachable`, `recent_daily_present`. Prints a human-readable report when run as `__main__`.

- [ ] **Step 1: Write `templates/config.example.yaml`**

Copy the Task 3 fixture content and prefix it with comment lines documenting each key (one `#` comment per non-obvious field: `planner_address`, `gdoc_id` — note it accepts either the full Google Docs URL or a bare ID, `converter_command` `{input}/{output}`, `obsidian.cert_path`, `llm.backend`).

- [ ] **Step 2: Write `templates/Daily.md`** — paste the user's provided Templater daily template verbatim (the `<%* … %>` block with the `## Notes`, `## TODO`, `### Completed / Cancelled`, `### References` Dataview sections).

- [ ] **Step 3: Write the failing test**

`tests/test_status_check.py`:
```python
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
```

Add `tests/conftest.py` so the sibling script imports:
```python
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # planner-setup/scripts
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))  # planner-setup (status_check.py)
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest tests/test_status_check.py -v`
Expected: FAIL (`ModuleNotFoundError: status_check`).

- [ ] **Step 5: Write `status_check.py`**

```python
"""Idempotent readiness probe used by the planner-setup skill."""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from planner.config import load_config  # noqa: E402
from planner.errors import ConfigError  # noqa: E402


def check(config_path: str) -> dict[str, bool]:
    """Return readiness flags for each setup prerequisite."""
    flags = {"config_present": Path(os.path.expanduser(config_path)).is_file(),
             "config_valid": False, "token_present": False, "obsidian_env_set": False,
             "vault_reachable": False, "recent_daily_present": False}
    try:
        cfg = load_config(config_path)
    except ConfigError:
        return flags
    flags["config_valid"] = True
    flags["token_present"] = Path(cfg.google.token_path).is_file()
    flags["obsidian_env_set"] = bool(os.environ.get(cfg.obsidian.api_key_env))
    daily_dir = Path(cfg.vault.path) / cfg.vault.daily_output_dir
    flags["vault_reachable"] = Path(cfg.vault.path).is_dir()
    for delta in range(0, 3):
        d = date.today() - timedelta(days=delta)
        if (daily_dir / f"{d.isoformat()}.md").is_file():
            flags["recent_daily_present"] = True
            break
    return flags


def main() -> None:
    """Print a readiness report for config.yaml (or $PLANNER_CONFIG)."""
    path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PLANNER_CONFIG", "config.yaml")
    for name, ok in check(path).items():
        print(f"[{'x' if ok else ' '}] {name}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_status_check.py -v`
Expected: `2 passed`.

- [ ] **Step 7: Commit**

```bash
git add plugins/wp-labs-planner/skills/planner-setup/scripts/templates plugins/wp-labs-planner/skills/planner-setup/status_check.py plugins/wp-labs-planner/skills/planner-setup/scripts/tests/test_status_check.py plugins/wp-labs-planner/skills/planner-setup/scripts/tests/conftest.py
git commit -m "feat(planner): config example, Daily template, status check"
```

---

### Task 15: `planner-setup` SKILL.md, README, launchd examples

**Files:**
- Create: `plugins/wp-labs-planner/skills/planner-setup/SKILL.md`
- Create: `plugins/wp-labs-planner/README.md`
- Create: `plugins/wp-labs-planner/skills/planner-setup/scripts/templates/launchd/com.wp-labs.planner.daily.plist`
- Create: `plugins/wp-labs-planner/skills/planner-setup/scripts/templates/launchd/com.wp-labs.planner.weekly.plist`
- Modify: `plugins/wp-labs-planner/.claude-plugin/plugin.json` (bump description; no code change needed to `.mcp.json`)

**Interfaces:**
- Produces: the user-facing skill that runs `status_check.py`, reports each flag, and walks the user through any missing prerequisite; the README setup walkthrough; macOS scheduler examples.

- [ ] **Step 1: Write `SKILL.md`**

```markdown
---
name: planner-setup
description: Check whether the wp-labs-planner is installed/configured/scheduled and, if not, walk the user through setup (Python env, Google OAuth, OneNote converter, LLM backend, Obsidian Local REST API + key, templates, schedule).
---

# Planner Setup

Use when the user wants to install, configure, or check the status of the wp-labs-planner.

## Steps

1. **Run the status check.** From `${CLAUDE_PLUGIN_ROOT}/skills/planner-setup`:
   `python3 status_check.py <config_path>` (default `config.yaml`). Report each flag.
2. **For each unmet flag, walk the fix** (idempotent — safe to re-run):
   - `config_present`/`config_valid`: copy `scripts/templates/config.example.yaml` to the
     user's `config.yaml`; fill `planner_address`, `gdoc_id`, vault paths.
   - `token_present`: have them create a Google Cloud OAuth desktop client (Gmail +
     Docs read-only scopes), save `credentials.json`, then run `python -m planner.daily`
     once to trigger the consent flow (writes `token.json`).
   - `obsidian_env_set`: install + enable the Obsidian **Local REST API** plugin, copy
     its API key, and `export OBSIDIAN_API_KEY=<key>` in the shell profile. Trust the
     self-signed cert (download from `https://127.0.0.1:27124/obsidian-local-rest-api.crt`
     into `obsidian.cert_path`, or set `NODE_EXTRA_CA_CERTS` for the bundled MCP server).
   - `vault_reachable`: verify `vault.path`; copy `templates/Daily.md` and
     `templates/Weekly.md` into `vault/<templates_dir>`.
   - OneNote converter + LLM backend: see README.
3. **Offer scheduling** (optional): install the launchd plists from
   `scripts/templates/launchd/` (daily, plus weekly on Fridays).
4. **Confirm:** re-run `status_check.py`; "running" = all flags except optional schedule.
```

- [ ] **Step 2: Write the launchd plists**

`…/templates/launchd/com.wp-labs.planner.daily.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.wp-labs.planner.daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string><string>-lc</string>
    <string>cd /PATH/TO/scripts &amp;&amp; uv run python -m planner.daily --config /PATH/TO/config.yaml</string>
  </array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>30</integer></dict>
  <key>StandardErrorPath</key><string>/tmp/planner.daily.log</string>
  <key>StandardOutPath</key><string>/tmp/planner.daily.log</string>
</dict>
</plist>
```

`…/templates/launchd/com.wp-labs.planner.weekly.plist`: same shape, `Label` `…weekly`, command `python -m planner.weekly`, `StartCalendarInterval` with `<key>Weekday</key><integer>5</integer>` (Friday) `Hour` 16.

- [ ] **Step 3: Write `README.md`**

Cover, in order: prerequisites (Python ≥3.11, `uv`); `uv venv && uv pip install -e ".[dev]"`; Google Cloud OAuth client (Gmail + Docs scopes) → `credentials.json`; OneNote converter install + `converter_command` `{input}/{output}`; LLM backend (`claude -p` default; or local Ollama — `llm.backend: local`, `model`, `endpoint`); Obsidian Local REST API plugin + `export OBSIDIAN_API_KEY` + cert trust (`obsidian.cert_path` / `NODE_EXTRA_CA_CERTS`); copy `config.example.yaml` → `config.yaml`; copy `Daily.md`/`Weekly.md` into the vault; `python -m planner.daily` / `python -m planner.weekly`; optional launchd (note `.zshenv` for unattended env, daily + Friday weekly).

- [ ] **Step 4: Update `plugin.json` description**

Set `description` to: `"Daily & weekly Obsidian planner: aggregates Gmail (+planner alias), a Google Doc, OneNote, and vault state into Obsidian notes via the Local REST API MCP. Includes the planner-setup skill."`

- [ ] **Step 5: Verify the skill files load (lint markdown frontmatter + JSON)**

```bash
python3 -c "import json; json.load(open('plugins/wp-labs-planner/.claude-plugin/plugin.json')); json.load(open('plugins/wp-labs-planner/.mcp.json')); print('json ok')"
head -3 plugins/wp-labs-planner/skills/planner-setup/SKILL.md   # frontmatter present
```
Expected: `json ok`; SKILL.md begins with `---`/`name:`.

- [ ] **Step 6: Final full verification**

```bash
cd plugins/wp-labs-planner/skills/planner-setup/scripts
uv run pytest -v && uv run ruff check planner && uv run mypy planner
```
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add plugins/wp-labs-planner
git commit -m "feat(planner): planner-setup skill, README, launchd examples"
```

---

## Self-Review

**1. Spec coverage**

| Spec section | Task(s) |
| --- | --- |
| §3 Gmail (accomplishments + calls) | 7 |
| §3 Google Doc todos | 8 |
| §3 OneNote `.one` → md (placeholder on fail) | 8 |
| §3 vault (projects, recent notes, git) | 6 |
| §4 priority emojis / `#project` / members / exclude templates | 2, 6, 10, 11 |
| §5 architecture / package layout | 1–13 |
| §5.1 `planner-setup` status check | 14, 15 |
| §5.2 native `/mcp/` client + filesystem fallback + TLS cert | 4, 5 |
| §5.2 `command_execute` daily-notes / `periodic_note_path` | 10 |
| §6 daily flow (sections, per-event headers, prev summary) | 10, 13 |
| §6 weekly flow (Dataview + static snapshot, `## Status`/`## Timeline`) | 11, 13 |
| §6 commit step | 12, 13 |
| §7 config schema | 3 |
| §8 OneNote risk (pluggable converter) | 8 |
| §9 error handling (degrade to placeholder, LLM-fail banner) | 8, 13 |
| §10 testing | every task |
| §11 README / setup | 15 |
| `llm.backend` claude/local | 9 |

No gaps found.

**2. Placeholder scan:** every code step contains complete code; no "TBD"/"add error handling"/"similar to". The two spec §12 items deferred to first-live-run (exact `vault_*` MCP arg names; fresh-note Templater expansion) are flagged inline in Task 5 and handled by graceful fallbacks (Task 10 `ensure_daily_note` stub), not left as plan placeholders.

**3. Type consistency:** `Vault` protocol methods (Task 4) are used with identical signatures in `McpVault` (5), collectors (6), and renderers (10–11). `Config` dataclass field names (Task 3) match every `cfg.vault.*`/`cfg.obsidian.*`/`cfg.llm.*` access downstream. Synthesis output keys (`calls`/`accomplishments_md`/`learnings_md`/`new_tasks`; `projects`/`groups`) are produced in Task 9's prompts and consumed with the same keys in Tasks 10–11. `commit_files`/`is_git_repo` (Task 12) are called with matching signatures in Task 13.
