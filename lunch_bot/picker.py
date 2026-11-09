from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date

from .config import CANDIDATE_COUNT, FORTUNE_PICK_COUNT, FORTUNE_WEIGHT, MAX_PRICE_BAND
from .market import StockQuote, fits_market, market_factor
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


def _matches_fortune(candidate: Candidate, favored: set[str]) -> bool:
    return bool(favored & set(candidate.shop["category"]))


def _weight(candidate: Candidate, favored: set[str], quote: StockQuote | None) -> float:
    fortune = FORTUNE_WEIGHT if _matches_fortune(candidate, favored) else 1.0
    return fortune * market_factor(candidate.shop, quote)


def _without_categories_of(
    pool: list[Candidate], chosen: list[Candidate]
) -> list[Candidate]:
    """Prefer shops sharing no category with those already chosen; fall back to
    any unchosen shop when that leaves nothing."""
    taken = {category for c in chosen for category in c.shop["category"]}
    unchosen = [c for c in pool if all(c is not picked for picked in chosen)]
    return [c for c in unchosen if not taken & set(c.shop["category"])] or unchosen


def _draw(
    pool: list[Candidate],
    picks: list[Candidate],
    favored: set[str],
    rng: random.Random,
    quote: StockQuote | None,
) -> list[Candidate]:
    picks = list(picks)
    pool = _without_categories_of(pool, picks)
    while pool and len(picks) < CANDIDATE_COUNT:
        matching = [c for c in pool if _matches_fortune(c, favored)]
        if len(picks) < FORTUNE_PICK_COUNT:
            options = matching if not picks and matching else pool
            weights = [_weight(c, favored, quote) for c in options]
            chosen = rng.choices(options, weights=weights)[0]
        else:
            chosen = rng.choice(pool)
        picks.append(chosen)
        pool = _without_categories_of(pool, picks)
    return picks


def pick_suggestions(
    candidates: list[Candidate],
    favored: set[str],
    rng: random.Random,
    quote: StockQuote | None = None,
) -> list[Candidate]:
    """Picks come from shops fitting the market mood (加菜 → $$+, 省一點 → $),
    topped up from the rest only when too few fit. Within that, the first
    pick always matches the fortune (when any shop does), the first two are
    weighted, and the last is random so the horoscope never decides alone."""
    fitting = [c for c in candidates if fits_market(c.shop, quote)]
    picks = _draw(fitting, [], favored, rng, quote)
    if len(picks) < CANDIDATE_COUNT:
        others = [c for c in candidates if not fits_market(c.shop, quote)]
        picks = _draw(others, picks, favored, rng, quote)
    return picks
