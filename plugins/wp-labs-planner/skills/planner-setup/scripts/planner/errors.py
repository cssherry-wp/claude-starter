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
    """Return the Tasks-plugin emoji for a priority level, or "" if unknown.

    Args:
        level: Priority level string (case-insensitive, whitespace-trimmed).

    Returns:
        The emoji string for the priority level, or "" if unknown.
    """
    return PRIORITY_EMOJI.get(level.strip().lower(), "")


def priority_rank(level: str) -> int:
    """Return the sort rank for a priority level (0 = highest).

    The ordering is derived from ``PRIORITY_EMOJI`` so the rank and emoji never
    drift apart. Unknown or blank levels rank as "medium".

    Args:
        level: Priority level string (case-insensitive, whitespace-trimmed).

    Returns:
        Zero-based rank; lower sorts first.
    """
    keys = list(PRIORITY_EMOJI)
    norm = level.strip().lower()
    return keys.index(norm) if norm in keys else keys.index("medium")
