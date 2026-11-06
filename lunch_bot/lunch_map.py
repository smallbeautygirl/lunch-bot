from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date

import requests

from .config import HTTP_TIMEOUT_SECONDS, LUNCH_MAP_BASE_URL, SHOPS_CACHE_PATH
from .market import MarketQuote, parse_quote

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LunchMapData:
    shops: list[dict]
    parkings: list[dict]
    settings: dict
    cached_on: str | None = None


def _fetch_json(path: str) -> list | dict:
    response = requests.get(f"{LUNCH_MAP_BASE_URL}{path}", timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def load_lunch_map(today: date) -> LunchMapData:
    """Fetch live data once a day; fall back to the last good snapshot so an
    outage on the lunch-map site still yields a lunch suggestion."""
    try:
        data = LunchMapData(
            shops=_fetch_json("/api/shops"),
            parkings=_fetch_json("/api/parkings"),
            settings=_fetch_json("/api/config"),
        )
    except (requests.RequestException, ValueError) as error:
        logger.warning(
            "Lunch map unavailable, using cache", extra={"error": str(error)}
        )
        return _read_cache()
    _save_cache(data, today)
    return data


def fetch_market_quote() -> MarketQuote | None:
    """Previous close of TAIEX as the site reports it. Never cached: a stale
    quote would steer lunch by an old day's market."""
    try:
        return parse_quote(_fetch_json("/api/market"))
    except (requests.RequestException, ValueError) as error:
        logger.warning("Market quote unavailable", extra={"error": str(error)})
        return None


def _save_cache(data: LunchMapData, today: date) -> None:
    payload = {
        "cached_on": today.isoformat(),
        "shops": data.shops,
        "parkings": data.parkings,
        "settings": data.settings,
    }
    SHOPS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SHOPS_CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1))


def _read_cache() -> LunchMapData:
    payload = json.loads(SHOPS_CACHE_PATH.read_text())
    return LunchMapData(
        shops=payload["shops"],
        parkings=payload["parkings"],
        settings=payload["settings"],
        cached_on=payload["cached_on"],
    )
