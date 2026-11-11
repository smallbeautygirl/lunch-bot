"""11:00 entry point: decide what kind of day it is, build the card, post it.

python -m lunch_bot.main            # post to TEAMS_WEBHOOK_URL
python -m lunch_bot.main --dry-run  # print the payload, post nothing
python -m lunch_bot.main --date 2026-11-09 --dry-run
"""

from __future__ import annotations

import logging
import random
from datetime import date, datetime

from .calendar_tw import DayKind, classify_day, fetch_holiday_flags
from .card import build_holiday_card, build_workday_card
from .config import HISTORY_PATH, TAIPEI, read_lunch_chief
from .content import extras_for, generate_content
from .history import has_posted_on, load_history, recent_shop_ids, save_suggestion
from .lunch_map import load_lunch_map
from .mafalda import fetch_mafalda_reading
from .parking import fetch_parking_catalog
from .picker import find_candidates, pick_suggestions
from .roles import read_member_roles, role_mixes
from .sign_sources import collect_sources
from .stocks import TAIEX, fetch_stock
from .teams import (
    configure_logging,
    deliver,
    is_past_deadline,
    parse_cli_args,
)
from .weekly_reading import fetch_weekly_reading
from .zodiac import ZODIAC_SIGNS, read_group_members

logger = logging.getLogger(__name__)


def build_workday_payload(day: date, rng: random.Random) -> tuple[dict, list[str]]:
    lunch_map = load_lunch_map(day)
    quote = fetch_stock(*TAIEX)
    excluded = recent_shop_ids(load_history(HISTORY_PATH), day)
    candidates = find_candidates(
        lunch_map.shops,
        lunch_map.parkings,
        lunch_map.settings,
        day=day,
        excluded=excluded,
    )
    categories = sorted({c for cand in candidates for c in cand.shop["category"]})
    # Draw from the group's own signs so the lucky sign is somebody's.
    members = read_group_members()
    sign = rng.choice(list(members) or ZODIAC_SIGNS)
    sources = collect_sources(
        [sign], fetch_weekly_reading(day), fetch_mafalda_reading(day, [sign])
    )[sign]
    content = generate_content(
        day=day,
        sign=sign,
        categories=categories,
        extras=extras_for(day, DayKind.WORKDAY),
        rng=rng,
        sources=sources,
        mood=quote.mood if quote else None,
        mix=role_mixes({sign: members.get(sign, [])}, read_member_roles()).get(
            sign, ""
        ),
    )
    picks = pick_suggestions(candidates, set(content.favored_categories), rng, quote)
    catalog = fetch_parking_catalog()
    parking = (
        {pick.shop["id"]: catalog.near(pick.shop) for pick in picks} if catalog else {}
    )
    card = build_workday_card(
        day=day,
        sign=sign,
        content=content,
        picks=picks,
        chief=read_lunch_chief(),
        cached_on=lunch_map.cached_on,
        quote=quote,
        sign_members=members.get(sign),
        sign_label=sources.label,
        parking=parking,
        parking_as_of=catalog.as_of if catalog else None,
    )
    return card, [pick.shop["id"] for pick in picks]


def build_holiday_payload(day: date, rng: random.Random) -> dict:
    content = generate_content(
        day=day,
        sign=None,
        categories=[],
        extras=extras_for(day, DayKind.NATIONAL_HOLIDAY),
        rng=rng,
    )
    return build_holiday_card(day=day, content=content)


def run() -> None:
    configure_logging()
    args = parse_cli_args("Lunch suggestion bot")
    if is_past_deadline(args.not_after, datetime.now(TAIPEI)):
        return
    day = args.date or datetime.now(TAIPEI).date()
    kind = classify_day(day, fetch_holiday_flags(day.year))
    logger.info("Day classified", extra={"day": day.isoformat(), "kind": kind})
    if kind is DayKind.WEEKEND:
        return
    is_real_post = not (args.test or args.dry_run)
    if is_real_post and has_posted_on(load_history(HISTORY_PATH), day):
        # An on-time external trigger and a late GitHub schedule can both fire;
        # the workflow's concurrency group makes the second see the first's
        # committed history.
        logger.info("Already posted today, skipping")
        return
    rng = random.Random(day.isoformat())
    shop_ids: list[str] = []
    if kind is DayKind.WORKDAY:
        payload, shop_ids = build_workday_payload(day, rng)
    else:
        payload = build_holiday_payload(day, rng)
    deliver(payload, dry_run=args.dry_run, is_test=args.test, note=args.note)
    if shop_ids and is_real_post:
        save_suggestion(HISTORY_PATH, day, shop_ids)


if __name__ == "__main__":
    run()
