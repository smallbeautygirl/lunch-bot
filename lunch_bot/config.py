from __future__ import annotations

import os
from datetime import timedelta, timezone
from pathlib import Path

TAIPEI = timezone(timedelta(hours=8))

LUNCH_MAP_BASE_URL = "https://lunch-map.betoolman.com"
TW_CALENDAR_URL = "https://cdn.jsdelivr.net/gh/ruyut/TaiwanCalendar/data/{year}.json"
HTTP_TIMEOUT_SECONDS = 15

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SHOPS_CACHE_PATH = DATA_DIR / "shops_cache.json"
HISTORY_PATH = DATA_DIR / "history.json"

CANDIDATE_COUNT = 3
FORTUNE_PICK_COUNT = 2
FORTUNE_WEIGHT = 3.0
RECENT_DAYS_EXCLUDED = 5
MAX_PRICE_BAND = 3

CLAUDE_MODEL = "claude-haiku-5-5"


def read_lunch_chief() -> tuple[str, str] | None:
    """Email + display name of the lunch chief, kept in secrets so the public
    repo never carries a colleague's address."""
    email = os.getenv("LUNCH_CHIEF_EMAIL", "").strip()
    if not email:
        return None
    return email, os.getenv("LUNCH_CHIEF_NAME", "午餐長").strip() or "午餐長"


def read_webhook_url() -> str | None:
    return os.getenv("TEAMS_WEBHOOK_URL", "").strip() or None
