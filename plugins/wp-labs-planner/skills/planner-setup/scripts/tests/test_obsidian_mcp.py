from __future__ import annotations

import json
from typing import Any

import pytest

from pathlib import Path

from planner.config import load_config
from planner.errors import VaultIOError
import planner.obsidian_mcp as mcp_mod
from planner.obsidian_mcp import _parse_sse

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
                # The real server returns the note as a JSON envelope, not raw text.
                envelope = json.dumps({
                    "tags": [], "frontmatter": {},
                    "stat": {"ctime": 1, "mtime": 2, "size": 30},
                    "path": "note.md",
                    "content": "## Notes\n\n- old\n\n## TODO\n",
                    "links": [], "backlinks": [],
                })
                return _content(envelope), session
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


def test_read_returns_content_not_envelope(vault: mcp_mod.McpVault) -> None:
    body = vault.read("note.md")
    assert body == "## Notes\n\n- old\n\n## TODO\n"
    assert "stat" not in body and "frontmatter" not in body  # envelope unwrapped


def test_patch_heading_calls_vault_patch(vault: mcp_mod.McpVault) -> None:
    vault.patch_heading("note.md", "Notes", "- x", operation="append")
    names = [c["params"]["name"] for c in vault._transport.calls if c.get("method") == "tools/call"]
    assert "vault_patch" in names


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OBSIDIAN_API_KEY", raising=False)
    cfg = load_config(str(FIXTURE))
    with pytest.raises(VaultIOError, match="OBSIDIAN_API_KEY"):
        mcp_mod.McpVault(cfg, transport=FakeTransport())


def test_parse_sse_picks_last_json() -> None:
    text = "event: message\ndata: {\"result\": {\"x\": 1}}\ndata: [DONE]"
    assert _parse_sse(text) == {"result": {"x": 1}}
    assert _parse_sse("no data here") == {}
