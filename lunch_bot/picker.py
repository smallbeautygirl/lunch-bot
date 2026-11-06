from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date

from .config import CANDIDATE_COUNT, FORTUNE_PICK_COUNT, FORTUNE_WEIGHT, MAX_PRICE_BAND
from .travel import Travel, estimate_travel

WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MINUTES_PER_DAY = 1440
EAT_IN_SERVICES = {"dine_in", "takeout"}


@dataclass(frozen=True)
class Candidate:
    shop: dict
    travel: Travel


def _to_minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def is_open_at(shop: dict, day: date, clock: str) -> bool:
    if shop.get("hoursUnknown"):
        return False
    moment = _to_minutes(clock)
    for start, end in shop.get("hours", {}).get(WEEKDAY_KEYS[day.weekday()], []):
        opens, closes = _to_minutes(start), _to_minutes(end)
        if closes <= opens:
            closes += MINUTES_PER_DAY
        if opens <= moment < closes:
            return True
    return False


def _is_eligible(shop: dict, day: date, depart: str, excluded: set[str]) -> bool:
    price = shop.get("price")
    return (
        shop["id"] not in excluded
        and not shop.get("needsReview")
        and bool(EAT_IN_SERVICES & set(shop.get("service") or []))
        and (price is None or price <= MAX_PRICE_BAND)
        and is_open_at(shop, day, depart)
    )


def find_candidates(
    shops: list[dict],
    parkings: list[dict],
    settings: dict,
    *,
    day: date,
    excluded: set[str],
) -> list[Candidate]:
    depart = settings["depart"]["start"]
    candidates = []
    for shop in shops:
        if not _is_eligible(shop, day, depart, excluded):
            continue
        travel = estimate_travel(shop, parkings, settings)
        if travel is not None:
            candidates.append(Candidate(shop, travel))
    return candidates


def _weight(candidate: Candidate, favored: set[str]) -> float:
    return FORTUNE_WEIGHT if favored & set(candidate.shop["category"]) else 1.0


def pick_suggestions(
    candidates: list[Candidate], favored: set[str], rng: random.Random
) -> list[Candidate]:
    """First pick always matches the fortune (when any shop does), so the card
    never recommends ramen and then lists none; then a fortune-weighted pick;
    the last is fully random so the horoscope never decides the whole list."""
    pool = list(candidates)
    picks: list[Candidate] = []
    while pool and len(picks) < CANDIDATE_COUNT:
        matching = [c for c in pool if _weight(c, favored) > 1.0]
        if not picks and matching:
            chosen = rng.choice(matching)
        elif len(picks) < FORTUNE_PICK_COUNT:
            weights = [_weight(c, favored) for c in pool]
            chosen = rng.choices(pool, weights=weights)[0]
        else:
            chosen = rng.choice(pool)
        picks.append(chosen)
        chosen_categories = set(chosen.shop["category"])
        narrowed = [c for c in pool if not chosen_categories & set(c.shop["category"])]
        pool = narrowed or [c for c in pool if c is not chosen]
    return picks
