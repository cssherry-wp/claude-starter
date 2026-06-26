from __future__ import annotations

import planner


def test_version_present() -> None:
    assert planner.__version__ == "0.1.0"


def test_daily_module_uses_gsheet_not_gdoc() -> None:
    import planner.daily as daily
    src = __import__("inspect").getsource(daily)
    assert "gsheet" in src
    # cfg.google.gdoc_id is the (legacy-named) sheet-ID config field — that's fine.
    # Guard: the gdoc *module* must not be imported or called.
    assert "import gdoc" not in src
    assert "gdoc.fetch" not in src


def test_gdoc_module_removed() -> None:
    import importlib
    try:
        importlib.import_module("planner.collectors.gdoc")
    except ModuleNotFoundError:
        return
    raise AssertionError("planner.collectors.gdoc should be removed")
