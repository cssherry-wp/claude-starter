"""Vault I/O abstraction: filesystem and native /mcp/ backends."""
from __future__ import annotations

import re
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
    match = re.search(rf"^## {re.escape(heading)}[ \t]*$", body, re.MULTILINE)
    if match is None:
        raise VaultIOError(f"Heading '## {heading}' not found")
    after = match.end()
    nxt = re.search(r"^## ", body[after:], re.MULTILINE)
    section_end = len(body) if nxt is None else after + nxt.start()
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
        """Return sorted entry names in dirpath, directories suffixed with '/'."""
        d = self._abs(dirpath)
        if not d.is_dir():
            raise VaultIOError(f"Not a directory: {dirpath}")
        return sorted(e.name + ("/" if e.is_dir() else "") for e in d.iterdir())

    def read(self, filepath: str) -> str:
        """Return the UTF-8 text content of filepath, raising VaultIOError if absent."""
        p = self._abs(filepath)
        if not p.is_file():
            raise VaultIOError(f"File not found: {filepath}")
        return p.read_text(encoding="utf-8")

    def stat_mtime(self, filepath: str) -> float:
        """Return the last-modified timestamp of filepath as a POSIX float."""
        p = self._abs(filepath)
        if not p.is_file():
            raise VaultIOError(f"File not found: {filepath}")
        return p.stat().st_mtime

    def write(self, filepath: str, content: str) -> None:
        """Write content to filepath, creating parent directories as needed."""
        p = self._abs(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def append(self, filepath: str, content: str) -> None:
        """Append content to filepath, creating it if it does not exist."""
        existing = self.read(filepath) if self.exists(filepath) else ""
        self.write(filepath, existing + ("\n" if existing and not existing.endswith("\n") else "") + content)

    def patch_heading(self, filepath: str, heading: str, content: str,
                      operation: str = "append") -> None:
        """Insert content under the named heading using append or prepend."""
        self.write(filepath, _insert_under_heading(self.read(filepath), heading, content, operation))

    def exists(self, filepath: str) -> bool:
        """Return True if filepath exists as a regular file."""
        return self._abs(filepath).is_file()


def make_vault(cfg: Config) -> Vault:
    """Return the configured vault backend."""
    if cfg.obsidian.mode == "filesystem":
        return FilesystemVault(cfg.vault.path)
    from planner.obsidian_mcp import McpVault  # local import to keep deps lazy

    return McpVault(cfg)
