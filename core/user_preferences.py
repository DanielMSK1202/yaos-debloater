"""Local, user-authored app notes; kept separate from analyzer conclusions."""
from __future__ import annotations

import json
import sys
from core.app_paths import data_dir
from pathlib import Path

PREFERENCES_PATH = data_dir() / "user_preferences.json" if getattr(sys, "frozen", False) else Path(__file__).with_name("user_preferences.json")
VALID_PREFERENCES = {"keep", "dont_need", "unsure"}


def load_preferences(path: str | Path = PREFERENCES_PATH) -> dict[str, str]:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return {key: value for key, value in raw.items() if value in VALID_PREFERENCES}
    except (OSError, ValueError, AttributeError):
        return {}


def save_preference(package: str, value: str, path: str | Path = PREFERENCES_PATH) -> dict[str, str]:
    if value not in VALID_PREFERENCES:
        raise ValueError("Unsupported user preference")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = load_preferences(target)
    existing[package] = value
    target.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return existing
