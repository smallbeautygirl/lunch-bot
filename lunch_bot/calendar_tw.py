from __future__ import annotations

import logging
from datetime import date
from enum import StrEnum

import requests

from .config import HTTP_TIMEOUT_SECONDS, TW_CALENDAR_URL

logger = logging.getLogger(__name__)

SATURDAY = 5


class DayKind(StrEnum):
    WORKDAY = "workday"
    NATIONAL_HOLIDAY = "national_holiday"
    WEEKEND = "weekend"


def classify_day(day: date, holiday_flags: dict[str, bool] | None) -> DayKind:
    """Weekday holidays get the light post; weekends stay silent unless the
    government calendar turns one into a make-up workday (補班)."""
    is_weekend = day.weekday() >= SATURDAY
    if holiday_flags is None or day.strftime("%Y%m%d") not in holiday_flags:
        return DayKind.WEEKEND if is_weekend else DayKind.WORKDAY
    if not holiday_flags[day.strftime("%Y%m%d")]:
        return DayKind.WORKDAY
    return DayKind.WEEKEND if is_weekend else DayKind.NATIONAL_HOLIDAY


def fetch_holiday_flags(year: int) -> dict[str, bool] | None:
    """Map of YYYYMMDD -> is_holiday, or None when the calendar is unreachable
    (callers then fall back to a plain Mon–Fri rule)."""
    url = TW_CALENDAR_URL.format(year=year)
    try:
        response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        return {row["date"]: bool(row["isHoliday"]) for row in response.json()}
    except (requests.RequestException, ValueError, KeyError) as error:
        logger.warning(
            "Taiwan calendar unavailable", extra={"year": year, "error": str(error)}
        )
        return None
