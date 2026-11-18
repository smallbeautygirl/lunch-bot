"""昨日群組回顧 for the morning card. It is written in a private repo (see
docs/adr/0001) and only read here: this repo and its logs are public, so the
text is never logged, and dry runs, which print the card, do not fetch it."""

from __future__ import annotations

import logging
import os
from datetime import date

import requests

from .config import HTTP_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

RECAP_URL = (
    "https://api.github.com/repos/smallbeautygirl/lunch-bot-private"
    "/contents/data/recap.json"
)
MONDAY = 0


def recap_title(day: date) -> str:
    return "上週五到週末的群組回顧" if day.weekday() == MONDAY else "昨日群組回顧"


def fetch_group_recap(day: date) -> str | None:
    """None without a token, when the private repo is unreachable, or when
    the recap there was not written for this day."""
    token = os.getenv("PRIVATE_REPO_TOKEN", "").strip()
    if not token:
        return None
    try:
        response = requests.get(
            RECAP_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.raw+json",
            },
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        saved = response.json()
    except (requests.RequestException, ValueError):
        logger.warning("Group recap unavailable")
        return None
    if saved.get("date") != day.isoformat():
        logger.warning("Group recap is not for today")
        return None
    return saved.get("recap") or None


def recap_lines(day: date, recap: str) -> list[str]:
    return [f"💬 **{recap_title(day)}**", recap]
