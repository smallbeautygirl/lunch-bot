"""Where to park near a drive-to shop: off-street car parks and curbside
segments in Kaohsiung, with live free spaces, from the MOTC's TDX open data.

lunch-map.betoolman.com only knows car parks around the office (it uses them
to time the drive), so the shop end comes from here. Spaces are as of the
card's 10:50 post, about an hour before anyone arrives: a hint, not a promise."""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime

import requests

from .config import HTTP_TIMEOUT_SECONDS, TAIPEI
from .travel import distance_meters

logger = logging.getLogger(__name__)

TOKEN_URL = (
    "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
)
API_BASE_URL = "https://tdx.transportdata.tw/api/basic/v1/Parking"
CITY = "Kaohsiung"
REQUEST_SPACING_SECONDS = 1.5
DEFAULT_RETRY_SECONDS = 5.0
MAX_ATTEMPTS = 3
HTTP_TOO_MANY_REQUESTS = 429
NEARBY_METERS = 300
CAR_SPACE_TYPE = 1
FARE_PATTERN = re.compile(r"(半小時|小時)\s*(\d+)\s*元")
FARE_UNITS = {"半小時": "半時", "小時": "時"}
CURB_FARE_PATTERNS = (
    (re.compile(r"半時計\s*(\d+)"), "半時"),
    (re.compile(r"計次\s*(\d+)"), "次"),
)


@dataclass(frozen=True)
class ParkingPlace:
    name: str
    lat: float
    lng: float
    fare: str | None
    free_spaces: int | None

    def as_point(self) -> dict:
        return {"lat": self.lat, "lng": self.lng}


@dataclass(frozen=True)
class ParkingOption:
    place: ParkingPlace
    meters: int


@dataclass(frozen=True)
class NearbyParking:
    lot: ParkingOption | None
    curb: ParkingOption | None


@dataclass(frozen=True)
class ParkingCatalog:
    lots: list[ParkingPlace]
    curbs: list[ParkingPlace]
    as_of: str

    def near(self, shop: dict) -> NearbyParking:
        return NearbyParking(
            lot=_best_nearby(self.lots, shop), curb=_best_nearby(self.curbs, shop)
        )


def _best_nearby(places: list[ParkingPlace], shop: dict) -> ParkingOption | None:
    """The nearest place with free spaces, else the nearest one at all."""
    options = [
        ParkingOption(place, round(distance_meters(shop, place.as_point())))
        for place in places
    ]
    nearby = sorted(
        (option for option in options if option.meters <= NEARBY_METERS),
        key=lambda option: option.meters,
    )
    with_space = [option for option in nearby if option.place.free_spaces != 0]
    return (with_space or nearby or [None])[0]


def short_lot_fare(description: str) -> str | None:
    match = FARE_PATTERN.search(description or "")
    if match is None:
        return None
    unit, price = match.groups()
    return f"${price}/{FARE_UNITS[unit]}"


def _car_free_spaces(availability: dict | None) -> int | None:
    for entry in (availability or {}).get("Availabilities", []):
        if entry.get("SpaceType") == CAR_SPACE_TYPE:
            return entry.get("AvailableSpaces")
    return None


def _takes_cars(car_park: dict, availability: dict | None) -> bool:
    if _car_free_spaces(availability) is not None:
        return True
    text = f"{car_park.get('Description', '')}{car_park.get('FareDescription', '')}"
    return "小型車" in text or "汽車" in text


def parse_lots(car_parks: list[dict], availabilities: list[dict]) -> list[ParkingPlace]:
    live = {entry["CarParkID"]: entry for entry in availabilities}
    lots = []
    for car_park in car_parks:
        availability = live.get(car_park["CarParkID"])
        position = car_park.get("CarParkPosition") or {}
        if not position or not _takes_cars(car_park, availability):
            continue
        lots.append(
            ParkingPlace(
                name=car_park["CarParkName"]["Zh_tw"],
                lat=position["PositionLat"],
                lng=position["PositionLon"],
                fare=short_lot_fare(car_park.get("FareDescription", "")),
                free_spaces=_car_free_spaces(availability),
            )
        )
    return lots


def short_curb_fare(description: str) -> str | None:
    """Curb fares come as codes like 半時計15 or 計次30; anything else (每6小時加簽一次,
    半時計高費率) means nothing to a reader and is left out."""
    for pattern, unit in CURB_FARE_PATTERNS:
        if match := pattern.search(description or ""):
            return f"${match.group(1)}/{unit}"
    return None


def parse_curbs(segments: list[dict], availabilities: list[dict]) -> list[ParkingPlace]:
    live = {entry["ParkingSegmentID"]: entry for entry in availabilities}
    curbs = []
    for segment in segments:
        position = segment.get("ParkingSegmentPosition") or {}
        if not position:
            continue
        availability = live.get(segment["ParkingSegmentID"])
        curbs.append(
            ParkingPlace(
                name=segment["ParkingSegmentName"]["Zh_tw"],
                lat=position["PositionLat"],
                lng=position["PositionLon"],
                fare=short_curb_fare(segment.get("FareDescription", "")),
                free_spaces=availability.get("AvailableSpaces")
                if availability
                else None,
            )
        )
    return curbs


def _read_credentials() -> tuple[str, str] | None:
    client_id = os.getenv("TDX_CLIENT_ID", "").strip()
    client_secret = os.getenv("TDX_CLIENT_SECRET", "").strip()
    return (client_id, client_secret) if client_id and client_secret else None


def _fetch_token(client_id: str, client_secret: str) -> str:
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _fetch_list(token: str, path: str, key: str) -> list[dict]:
    """TDX's free tier answers 429 to back-to-back calls, so every call is
    spaced out and a 429 is retried after the wait it asks for."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        time.sleep(REQUEST_SPACING_SECONDS)
        response = requests.get(
            f"{API_BASE_URL}/{path}/City/{CITY}",
            params={"$format": "JSON"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        if response.status_code != HTTP_TOO_MANY_REQUESTS or attempt == MAX_ATTEMPTS:
            break
        time.sleep(_retry_after_seconds(response))
    response.raise_for_status()
    return response.json()[key]


def _retry_after_seconds(response: requests.Response) -> float:
    try:
        return float(response.headers.get("Retry-After", DEFAULT_RETRY_SECONDS))
    except ValueError:
        return DEFAULT_RETRY_SECONDS


def fetch_parking_catalog() -> ParkingCatalog | None:
    """None without TDX credentials or when TDX is down; the card then simply
    goes out without parking lines."""
    credentials = _read_credentials()
    if credentials is None:
        return None
    try:
        token = _fetch_token(*credentials)
        lots = parse_lots(
            _fetch_list(token, "OffStreet/CarPark", "CarParks"),
            _fetch_list(
                token, "OffStreet/ParkingAvailability", "ParkingAvailabilities"
            ),
        )
        curbs = parse_curbs(
            _fetch_list(token, "OnStreet/ParkingSegment", "ParkingSegments"),
            _fetch_list(
                token,
                "OnStreet/ParkingSegmentAvailability",
                "CurbParkingSegmentAvailabilities",
            ),
        )
    except (requests.RequestException, KeyError, ValueError):
        logger.warning("TDX parking data unavailable", exc_info=True)
        return None
    return ParkingCatalog(
        lots=lots, curbs=curbs, as_of=datetime.now(TAIPEI).strftime("%H:%M")
    )
