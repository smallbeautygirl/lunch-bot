"""Exits non-zero when a workday's cards did not go out, so the failed
workflow run makes GitHub email the repo owner. Nothing is posted to the group.

python -m lunch_bot.watchdog [--date 2026-11-12]
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime

from .calendar_tw import DayKind, classify_day, fetch_holiday_flags
from .config import HISTORY_PATH, MORNING_POSTS_PATH, TAIPEI
from .history import has_posted_on, load_history, load_post_days

logger = logging.getLogger(__name__)


def missing_cards(day: date, kind: DayKind) -> list[str]:
    if kind is not DayKind.WORKDAY:
        return []
    missing = []
    if day.isoformat() not in load_post_days(MORNING_POSTS_PATH):
        missing.append("早安卡")
    if not has_posted_on(load_history(HISTORY_PATH), day):
        missing.append("午餐卡")
    return missing


def run() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    parser = argparse.ArgumentParser(description="Check today's cards went out")
    parser.add_argument("--date", type=date.fromisoformat)
    args = parser.parse_args()
    day = args.date or datetime.now(TAIPEI).date()
    missing = missing_cards(day, classify_day(day, fetch_holiday_flags(day.year)))
    if missing:
        print(f"::error::{day.isoformat()} 沒有發出：{'、'.join(missing)}")
        sys.exit(1)
    logger.info("All cards went out", extra={"day": day.isoformat()})


if __name__ == "__main__":
    run()
