"""Walk/drive estimate, mirroring lunch-map.betoolman.com's own formula so the
bot and the site never disagree about how far a shop is."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

EARTH_DIAMETER_METERS = 12_742_000


class TravelMode(StrEnum):
    WALK = "walk"
    DRIVE = "drive"


@dataclass(frozen=True)
class Travel:
    mode: TravelMode
    minutes: int


def distance_meters(origin: dict, destination: dict) -> float:
    to_rad = math.radians
    d_lat = to_rad(destination["lat"] - origin["lat"])
    d_lng = to_rad(destination["lng"] - origin["lng"])
    haversine = (
        math.sin(d_lat / 2) ** 2
        + math.cos(to_rad(origin["lat"]))
        * math.cos(to_rad(destination["lat"]))
        * math.sin(d_lng / 2) ** 2
    )
    return EARTH_DIAMETER_METERS * math.asin(math.sqrt(haversine))


def _minutes(meters: float, speed: float, settings: dict) -> int:
    return max(1, math.ceil(meters * settings["detour"] / speed))


def _drive_minutes(shop: dict, parkings: list[dict], settings: dict) -> int:
    office = settings["office"]
    street_search = 1 if shop.get("ownParking") else settings["streetSearch"]
    best = _minutes(distance_meters(office, shop), settings["driveSpeed"], settings)
    best += street_search
    for parking in parkings:
        via_parking = (
            _minutes(distance_meters(office, parking), settings["driveSpeed"], settings)
            + parking.get("searchMin", settings["parkSearch"])
            + _minutes(distance_meters(parking, shop), settings["walkSpeed"], settings)
        )
        best = min(best, via_parking)
    return best


def estimate_travel(shop: dict, parkings: list[dict], settings: dict) -> Travel | None:
    """None when the shop is beyond both the walking and the driving limit."""
    if shop.get("driveMin") is not None:
        walk, drive = math.inf, shop["driveMin"]
    else:
        meters = distance_meters(settings["office"], shop)
        walk = _minutes(meters, settings["walkSpeed"], settings)
        drive = _drive_minutes(shop, parkings, settings)
    can_walk = walk <= settings["maxWalkMin"]
    can_drive = drive <= settings["maxDriveMin"]
    if can_walk and can_drive and walk - drive >= settings["driveWorthIt"]:
        return Travel(TravelMode.DRIVE, drive)
    if can_walk:
        return Travel(TravelMode.WALK, int(walk))
    if can_drive:
        return Travel(TravelMode.DRIVE, drive)
    return None
