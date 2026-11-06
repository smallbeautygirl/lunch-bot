"""9:00 workday post: market snapshot plus a horoscope for the group's signs.

python -m lunch_bot.morning --dry-run
python -m lunch_bot.morning --date 2026-11-09 --dry-run
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from .calendar_tw import DayKind, classify_day, fetch_holiday_flags
from .config import TAIPEI
from .horoscope import generate_horoscope
from .morning_card import build_morning_card, stock_line
from .stocks import TAIEX, fetch_overseas, fetch_stock
from .teams import configure_logging, deliver, parse_cli_args
from .zodiac import ZODIAC_SIGNS, read_group_members

logger = logging.getLogger(__name__)


def build_morning_payload(day: date) -> dict:
    members = read_group_members()
    taiex = fetch_stock(*TAIEX)
    overseas = fetch_overseas()
    market_lines = [stock_line(quote) for quote in [taiex, *overseas] if quote]
    fortunes = generate_horoscope(
        day=day,
        signs=list(members) or list(ZODIAC_SIGNS),
        market_lines=market_lines,
    )
    return build_morning_card(
        day=day,
        taiex=taiex,
        overseas=overseas,
        fortunes=fortunes,
        members=members,
    )


def run() -> None:
    configure_logging()
    args = parse_cli_args("Morning horoscope and market post")
    day = args.date or datetime.now(TAIPEI).date()
    kind = classify_day(day, fetch_holiday_flags(day.year))
    logger.info("Day classified", extra={"day": day.isoformat(), "kind": kind})
    # Holidays and weekends repeat the last trading day's market; skip them.
    if kind is not DayKind.WORKDAY:
        return
    deliver(build_morning_payload(day), dry_run=args.dry_run, is_test=args.test)


if __name__ == "__main__":
    run()
