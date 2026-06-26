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
