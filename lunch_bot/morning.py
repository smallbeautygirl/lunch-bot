"""9:00 workday post: market snapshot plus a horoscope for the group's signs.

python -m lunch_bot.morning --dry-run
python -m lunch_bot.morning --date 2026-11-09 --dry-run
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from .calendar_tw import DayKind, classify_day, fetch_holiday_flags
from .config import MORNING_POSTS_PATH, TAIPEI
from .group_recap import fetch_group_recap
from .history import load_post_days, record_post_day
from .horoscope import generate_horoscope
from .mafalda import fetch_mafalda_reading
from .morning_card import HoroscopeContext, build_morning_card, stock_line
from .roles import read_member_roles, role_mixes
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


def build_morning_payload(day: date, *, with_recap: bool = False) -> dict:
    members = read_group_members()
    taiex = fetch_stock(*TAIEX)
    overseas = fetch_overseas()
    market_lines = [stock_line(quote) for quote in [taiex, *overseas] if quote]
    signs = list(members) or list(ZODIAC_SIGNS)
    tang = fetch_weekly_reading(day)
    mafalda = fetch_mafalda_reading(day, signs)
    sources = collect_sources(signs, tang, mafalda)
    fortunes = generate_horoscope(
        day=day,
        sources=sources,
        market_lines=market_lines,
        mixes=role_mixes(members, read_member_roles()),
    )
    context = HoroscopeContext(members=members, tang=tang, mafalda=mafalda)
    # Fetched even when left out, so a dry run still shows the token works.
    recap = fetch_group_recap(day)
    return build_morning_card(
        day=day,
        taiex=taiex,
        overseas=overseas,
        fortunes=fortunes,
        context=context,
        group_sections=recap if with_recap else [],
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
    is_real_post = not (args.test or args.dry_run)
    if is_real_post and day.isoformat() in load_post_days(MORNING_POSTS_PATH):
        # The crontab and a manual catch-up can both fire on the same day.
        logger.info("Already posted today, skipping")
        return
    deliver(
        # A dry run prints the card into a public Actions log.
        build_morning_payload(day, with_recap=not args.dry_run),
        dry_run=args.dry_run,
        is_test=args.test,
        note=args.note,
    )
    if is_real_post:
        record_post_day(MORNING_POSTS_PATH, day)


if __name__ == "__main__":
    run()
