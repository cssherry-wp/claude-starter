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
    """Return readiness flags for each setup prerequisite.

    Args:
        config_path: Path to the planner config.yaml file.

    Returns:
        Dict mapping flag names to their boolean readiness state.
    """
    flags = {
        "config_present": Path(os.path.expanduser(config_path)).is_file(),
        "config_valid": False,
        "token_present": False,
        "obsidian_env_set": False,
        "vault_reachable": False,
        "recent_daily_present": False,
    }
    try:
        cfg = load_config(config_path)
    except ConfigError:
        return flags
    flags["config_valid"] = True
    flags["token_present"] = Path(cfg.google.token_path).is_file()
    flags["obsidian_env_set"] = bool(os.environ.get(cfg.obsidian.api_key_env))
    daily_dir = Path(cfg.vault.path) / cfg.vault.daily_output_dir
    flags["vault_reachable"] = Path(cfg.vault.path).is_dir()
    for delta in range(3):
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
