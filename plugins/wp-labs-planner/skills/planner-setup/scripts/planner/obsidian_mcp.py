"""Native Obsidian /mcp/ server client (Streamable HTTP, JSON-RPC)."""
from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from typing import Any, Protocol

from planner.config import Config
from planner.errors import VaultIOError

log = logging.getLogger(__name__)

PROTOCOL_VERSION = "2025-06-18"


def _parse_sse(text: str) -> dict[str, Any]:
    """Return the last JSON-parseable ``data:`` line from an SSE response body.

    Non-JSON sentinel values such as ``data: [DONE]`` are silently skipped.

    Args:
        text: Raw SSE response text.

    Returns:
        Parsed dict from the last JSON ``data:`` line, or ``{}`` if none found.
    """
    last: dict[str, Any] = {}
    for line in text.splitlines():
        if line.startswith("data:"):
            candidate = line[len("data:"):].strip()
            try:
                last = json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return last


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
        """Send a JSON-RPC request and return (parsed payload, session id).

        Args:
            body: The JSON-RPC request body.
            session: The current MCP session id, or None for initialization.

        Returns:
            Tuple of (parsed response payload, session id from response header).
        """
        req = urllib.request.Request(self._url, method="POST", data=json.dumps(body).encode())
        req.add_header("Authorization", f"Bearer {self._key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        req.add_header("MCP-Protocol-Version", PROTOCOL_VERSION)
        if session:
            req.add_header("Mcp-Session-Id", session)
        try:
            with urllib.request.urlopen(req, context=self._ctx, timeout=30) as resp:
                sid = resp.headers.get("Mcp-Session-Id") or session
                text = resp.read().decode("utf-8")
        except (urllib.error.URLError, OSError) as exc:
            raise VaultIOError(f"MCP request to {self._url} failed: {exc}") from exc
        return _parse_sse(text), sid


class McpVault:
    """Vault backed by the plugin's native MCP server."""

    def __init__(self, cfg: Config, transport: Transport | None = None) -> None:
        key = os.environ.get(cfg.obsidian.api_key_env, "")
        if not key:
            raise VaultIOError(f"{cfg.obsidian.api_key_env} is not set in the environment")
        url = f"https://{cfg.obsidian.host}:{cfg.obsidian.port}/mcp/"
        self._transport: Transport = transport or HttpTransport(url, key, cfg.obsidian.cert_path)
        self._session: str | None = None
        self._req_id = 0

    def _ensure_session(self) -> None:
        if self._session:
            return
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "wp-labs-planner", "version": "0.1.0"},
            },
        }
        payload, sid = self._transport.post(body, None)
        if not sid:
            raise VaultIOError("MCP initialize did not return a session id")
        self._session = sid

    def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._ensure_session()
        self._req_id += 1
        body = {"jsonrpc": "2.0", "id": self._req_id, "method": method, "params": params}
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
        """Return entry names in dirpath, directories suffixed with '/'.

        Args:
            dirpath: Vault-relative directory path.

        Returns:
            List of entry names.

        Raises:
            VaultIOError: If the MCP call fails or response is not JSON.
        """
        raw = self._tool("vault_list", {"directory": dirpath})
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VaultIOError(f"vault_list returned non-JSON: {raw[:80]}") from exc
        files = data.get("files", data) if isinstance(data, dict) else data
        return list(files)

    def read(self, filepath: str) -> str:
        """Return the text content of filepath.

        Args:
            filepath: Vault-relative file path.

        Returns:
            File content as a string.

        Raises:
            VaultIOError: If the MCP call fails.
        """
        return self._tool("vault_read", {"path": filepath})

    def stat_mtime(self, filepath: str) -> float:
        """Return the last-modified timestamp of filepath as a POSIX float.

        Args:
            filepath: Vault-relative file path.

        Returns:
            Modification time in seconds since epoch, or 0.0 on parse failure.

        Raises:
            VaultIOError: If the MCP call fails.
        """
        raw = self._tool("vault_read", {"path": filepath, "includeStat": True})
        try:
            data = json.loads(raw)
            return float(data.get("stat", {}).get("mtime", 0)) / 1000.0
        except (json.JSONDecodeError, ValueError, AttributeError):
            log.warning("stat_mtime: vault_read returned non-JSON or stat unavailable for %s; returning 0.0", filepath)
            return 0.0

    def write(self, filepath: str, content: str) -> None:
        """Write content to filepath, overwriting any existing content.

        Args:
            filepath: Vault-relative file path.
            content: Text content to write.

        Raises:
            VaultIOError: If the MCP call fails.
        """
        self._tool("vault_write", {"path": filepath, "content": content})

    def append(self, filepath: str, content: str) -> None:
        """Append content to filepath.

        Args:
            filepath: Vault-relative file path.
            content: Text content to append.

        Raises:
            VaultIOError: If the MCP call fails.
        """
        self._tool("vault_append", {"path": filepath, "content": content})

    def patch_heading(
        self, filepath: str, heading: str, content: str, operation: str = "append"
    ) -> None:
        """Insert content under the named heading.

        Args:
            filepath: Vault-relative file path.
            heading: The heading text to target (without leading ##).
            content: Text content to insert.
            operation: Either "append" or "prepend". Defaults to "append".

        Raises:
            VaultIOError: If the MCP call fails.
        """
        self._tool(
            "vault_patch",
            {
                "path": filepath,
                "operation": operation,
                "targetType": "heading",
                "target": heading,
                "content": content,
            },
        )

    def exists(self, filepath: str) -> bool:
        """Return True if filepath exists as a readable file.

        Args:
            filepath: Vault-relative file path.

        Returns:
            True if the file exists, False otherwise.
        """
        try:
            self.read(filepath)
            return True
        except VaultIOError:
            return False

    def periodic_note_path(self, period: str) -> str | None:
        """Return the vault path for the given periodic note, or None if unavailable.

        Args:
            period: Period type (e.g. "daily", "weekly").

        Returns:
            Vault-relative path string, or None.
        """
        try:
            raw = self._tool("periodic_note_get_path", {"period": period})
        except VaultIOError:
            return None
        try:
            return json.loads(raw).get("path")
        except json.JSONDecodeError:
            return raw.strip() or None

    def execute_command(self, command_id: str) -> None:
        """Execute an Obsidian command by ID.

        Args:
            command_id: The command identifier to execute.

        Raises:
            VaultIOError: If the MCP call fails.
        """
        self._tool("command_execute", {"commandId": command_id})

    def search_query(self, query: dict[str, Any]) -> list[Any]:
        """Run a search query and return the results.

        Args:
            query: Search query dict passed to the vault search tool.

        Returns:
            List of search result items, empty list on parse failure.

        Raises:
            VaultIOError: If the MCP call fails.
        """
        raw = self._tool("search_query", {"query": query})
        try:
            return list(json.loads(raw))
        except json.JSONDecodeError:
            return []
