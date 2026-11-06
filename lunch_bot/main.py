"""Daily entry point: decide what kind of day it is, build the card, post it.

python -m lunch_bot.main            # post to TEAMS_WEBHOOK_URL
python -m lunch_bot.main --dry-run  # print the payload, post nothing
python -m lunch_bot.main --date 2026-11-09 --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from datetime import date, datetime

import requests

from .calendar_tw import DayKind, classify_day, fetch_holiday_flags
from .card import build_holiday_card, build_workday_card, mark_as_test
from .config import (
    HISTORY_PATH,
    HTTP_TIMEOUT_SECONDS,
    TAIPEI,
    read_lunch_chief,
    read_webhook_url,
)
from .content import ZODIAC_SIGNS, extras_for, generate_content
from .history import load_history, recent_shop_ids, save_suggestion
from .lunch_map import fetch_market_quote, load_lunch_map
from .picker import find_candidates, pick_suggestions

logger = logging.getLogger(__name__)


def build_workday_payload(day: date, rng: random.Random) -> tuple[dict, list[str]]:
    lunch_map = load_lunch_map(day)
    quote = fetch_market_quote()
    excluded = recent_shop_ids(load_history(HISTORY_PATH), day)
    candidates = find_candidates(
        lunch_map.shops,
        lunch_map.parkings,
        lunch_map.settings,
        day=day,
        excluded=excluded,
    )
    categories = sorted({c for cand in candidates for c in cand.shop["category"]})
    sign = rng.choice(ZODIAC_SIGNS)
    content = generate_content(
        day=day,
        sign=sign,
        categories=categories,
        extras=extras_for(day, DayKind.WORKDAY),
        rng=rng,
    )
    picks = pick_suggestions(candidates, set(content.favored_categories), rng, quote)
    card = build_workday_card(
        day=day,
        sign=sign,
        content=content,
        picks=picks,
        chief=read_lunch_chief(),
        cached_on=lunch_map.cached_on,
        quote=quote,
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


def send_to_teams(payload: dict) -> None:
    webhook_url = read_webhook_url()
    if webhook_url is None:
        raise SystemExit("TEAMS_WEBHOOK_URL is not set")
    response = requests.post(webhook_url, json=payload, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    logger.info("Posted to Teams", extra={"status": response.status_code})


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lunch suggestion bot")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument(
        "--test",
        action="store_true",
        help="Post with a [測試中] title and leave the suggestion history alone",
    )
    return parser.parse_args()


def run() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    args = _parse_args()
    day = args.date or datetime.now(TAIPEI).date()
    kind = classify_day(day, fetch_holiday_flags(day.year))
    logger.info("Day classified", extra={"day": day.isoformat(), "kind": kind})
    if kind is DayKind.WEEKEND:
        return
    rng = random.Random(day.isoformat())
    shop_ids: list[str] = []
    if kind is DayKind.WORKDAY:
        payload, shop_ids = build_workday_payload(day, rng)
    else:
        payload = build_holiday_payload(day, rng)
    if args.test:
        payload = mark_as_test(payload)
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    send_to_teams(payload)
    if shop_ids and not args.test:
        save_suggestion(HISTORY_PATH, day, shop_ids)


if __name__ == "__main__":
    run()
