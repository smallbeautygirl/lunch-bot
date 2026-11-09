from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .config import RECENT_DAYS_EXCLUDED

HISTORY_ENTRIES_KEPT = 60


def load_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text())


def has_posted_on(history: list[dict], day: date) -> bool:
    return any(entry["date"] == day.isoformat() for entry in history)


def recent_shop_ids(history: list[dict], today: date) -> set[str]:
    """Shops suggested on the last few posting days, not counting a rerun today."""
    earlier = [entry for entry in history if entry["date"] < today.isoformat()]
    recent = earlier[-RECENT_DAYS_EXCLUDED:]
    return {shop_id for entry in recent for shop_id in entry["shop_ids"]}


def save_suggestion(path: Path, today: date, shop_ids: list[str]) -> None:
    history = [e for e in load_history(path) if e["date"] != today.isoformat()]
    history.append({"date": today.isoformat(), "shop_ids": shop_ids})
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = history[-HISTORY_ENTRIES_KEPT:]
    path.write_text(json.dumps(kept, ensure_ascii=False, indent=1))
