from __future__ import annotations

from datetime import date
from pathlib import Path

import planner.daily as daily_mod
import planner.weekly as weekly_mod
from planner.config import load_config
from planner.errors import VaultIOError
from planner.obsidian import FilesystemVault

FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def test_merge_calls_uses_fetched_time_and_email_summary() -> None:
    """Title/time come from the parsed email; project from the LLM; email summary wins."""
    fetched = [{"title": "Demo Hour", "time": "10:00", "summary": "bring slides"}]
    llm = [{"title": "Demo Hour", "project": "#project/VIP", "previous_summary": "stale"}]
    assert daily_mod._merge_calls(fetched, llm) == [
        {"title": "Demo Hour", "time": "10:00", "project": "#project/VIP",
         "people": "", "previous_summary": "bring slides"}]


def test_merge_calls_keeps_events_without_llm_match() -> None:
    merged = daily_mod._merge_calls([{"title": "Solo", "time": "09:00", "summary": ""}], [])
    assert merged[0]["title"] == "Solo" and merged[0]["project"] == ""
    assert merged[0]["people"] == ""


def test_merge_calls_adds_people_tags_from_attendees() -> None:
    fetched = [{"title": "Demo Hour", "time": "18:00", "summary": "",
                "attendees": ["Sherry Zhou", "organized by PLACEHOLDER"]}]
    merged = daily_mod._merge_calls(fetched, [], ["#vip/ray_rouleau", "#wpl/sherry"])
    assert merged[0]["people"] == "#wpl/sherry"


def test_resolve_people_appends_new_attendees_to_template(tmp_path: Path) -> None:
    (tmp_path / "zz-Templates").mkdir()
    people = tmp_path / "zz-Templates" / "People.md"
    people.write_text("#wpl/sherry\n")
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.obsidian.mode = "filesystem"
    v = FilesystemVault(str(tmp_path))
    calls = [{"attendees": ["Sherry Zhou", "John Doe", "organized by PLACEHOLDER"]}]
    tags = daily_mod._resolve_people(v, cfg, calls)
    assert "#unsorted/john_doe" in tags
    body = people.read_text()
    assert "#unsorted/john_doe" in body  # new person persisted to the template
    assert body.count("#wpl/sherry") == 1  # known person not duplicated


def test_run_daily_apply_failure_does_not_abort(tmp_path: Path, monkeypatch) -> None:
    """run_daily reaches the commit check even when an apply call raises VaultIOError."""
    (tmp_path / "zz-Sherry_Daily").mkdir()
    (tmp_path / "zz-Sherry_Daily" / "2026-06-23.md").write_text("## Notes\n\n## TODO\n")
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.obsidian.mode = "filesystem"
    cfg.vault.git_commit = False

    def bad_apply_open(*_args, **_kwargs) -> None:
        raise VaultIOError("no Open Items heading")

    monkeypatch.setattr(daily_mod, "make_vault", lambda c: FilesystemVault(str(tmp_path)))
    monkeypatch.setattr(daily_mod, "_gather_daily", lambda vault, cfg, today: {"x": 1})
    monkeypatch.setattr(daily_mod, "synthesize_daily",
                        lambda cfg, tmpl, payload: {"calls": [], "accomplishments_md": "",
                                                    "learnings_md": "", "new_tasks": []})
    import planner.render_tasks as rt
    monkeypatch.setattr(rt, "apply_open_items", bad_apply_open)
    # Must not raise; must return a path
    result = daily_mod.run_daily(cfg, date(2026, 6, 23))
    assert result.endswith("2026-06-23.md")


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


def test_run_weekly_end_to_end(tmp_path: Path, monkeypatch) -> None:
    cfg = load_config(str(FIXTURE))
    cfg.vault.path = str(tmp_path)
    cfg.obsidian.mode = "filesystem"
    cfg.vault.git_commit = False
    monkeypatch.setattr(weekly_mod, "make_vault", lambda c: FilesystemVault(str(tmp_path)))
    monkeypatch.setattr(weekly_mod, "_gather_weekly", lambda vault, cfg: ({"projects": [], "open_tasks": []}, []))
    monkeypatch.setattr(weekly_mod, "synthesize_weekly", lambda cfg, tmpl, payload: {"projects": [], "groups": []})
    touched = weekly_mod.run_weekly(cfg, date(2026, 6, 26))
    assert any("week-overview" in p for p in touched)
    body = FilesystemVault(str(tmp_path)).read("zz-Sherry_Weekly/2026-06-26-week-overview.md")
    assert "Weekly" in body
