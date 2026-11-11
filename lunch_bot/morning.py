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
from .mafalda import fetch_mafalda_reading
from .morning_card import HoroscopeContext, build_morning_card, stock_line
from .sign_sources import collect_sources
from .stocks import TAIEX, fetch_overseas, fetch_stock
from .teams import (
    configure_logging,
    deliver,
    is_past_deadline,
    parse_cli_args,
)
from .weekly_reading import fetch_weekly_reading
from .zodiac import ZODIAC_SIGNS, read_group_members

logger = logging.getLogger(__name__)


def build_morning_payload(day: date) -> dict:
    members = read_group_members()
    taiex = fetch_stock(*TAIEX)
    overseas = fetch_overseas()
    market_lines = [stock_line(quote) for quote in [taiex, *overseas] if quote]
    signs = list(members) or list(ZODIAC_SIGNS)
    tang = fetch_weekly_reading(day)
    mafalda = fetch_mafalda_reading(day, signs)
    sources = collect_sources(signs, tang, mafalda)
    fortunes = generate_horoscope(day=day, sources=sources, market_lines=market_lines)
    context = HoroscopeContext(
        members=members, sources=sources, tang=tang, mafalda=mafalda
    )
    return build_morning_card(
        day=day,
        taiex=taiex,
        overseas=overseas,
        fortunes=fortunes,
        context=context,
    )


def run() -> None:
    configure_logging()
    args = parse_cli_args("Morning horoscope and market post")
    if is_past_deadline(args.not_after, datetime.now(TAIPEI)):
        return
    day = args.date or datetime.now(TAIPEI).date()
    kind = classify_day(day, fetch_holiday_flags(day.year))
    logger.info("Day classified", extra={"day": day.isoformat(), "kind": kind})
    # Holidays and weekends repeat the last trading day's market; skip them.
    if kind is not DayKind.WORKDAY:
        return
    deliver(
        build_morning_payload(day),
        dry_run=args.dry_run,
        is_test=args.test,
        note=args.note,
    )


if __name__ == "__main__":
    run()
