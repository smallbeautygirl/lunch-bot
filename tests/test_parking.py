from __future__ import annotations

from lunch_bot.card import parking_line
from lunch_bot.parking import (
    NearbyParking,
    ParkingCatalog,
    ParkingOption,
    ParkingPlace,
    parse_curbs,
    parse_lots,
    short_curb_fare,
    short_lot_fare,
)

SHOP = {"lat": 22.6200, "lng": 120.2800}
# ~0.0009° of latitude is ~100 m.
NEAR, FARTHER, TOO_FAR = 0.0009, 0.0018, 0.0036


def place(name: str, offset: float, free: int | None) -> ParkingPlace:
    return ParkingPlace(name, SHOP["lat"] + offset, SHOP["lng"], "$15/半時", free)


def car_park(car_park_id: str, description: str = "", fare: str = "") -> dict:
    return {
        "CarParkID": car_park_id,
        "CarParkName": {"Zh_tw": f"停車場{car_park_id}"},
        "CarParkPosition": {"PositionLat": 22.62, "PositionLon": 120.28},
        "Description": description,
        "FareDescription": fare,
    }


def test_lot_fare_is_shortened_to_price_per_period():
    assert short_lot_fare("小型車：半小時15元， 當日上限300元") == "$15/半時"
    assert short_lot_fare("當日上限300元") is None
    assert short_lot_fare("計時收費：每半小時50元 (當日最高500元)") == "$50/半時"
    assert short_lot_fare("每小時70元") == "$70/時"


def test_only_readable_curb_fares_are_kept():
    assert short_curb_fare("半時計15") == "$15/半時"
    assert short_curb_fare("計次30") == "$30/次"
    assert short_curb_fare("每6小時加簽一次") is None
    assert short_curb_fare("半時計高費率") is None


def test_motorcycle_only_lots_are_left_out():
    live = [
        {
            "CarParkID": "A",
            "Availabilities": [{"SpaceType": 1, "AvailableSpaces": 12}],
        }
    ]
    lots = parse_lots(
        [car_park("A"), car_park("B", "平面機車413格"), car_park("C", "小型車82格")],
        live,
    )
    assert [(lot.name, lot.free_spaces) for lot in lots] == [
        ("停車場A", 12),
        ("停車場C", None),
    ]


def test_curb_segments_carry_their_live_free_spaces():
    segments = [
        {
            "ParkingSegmentID": "440",
            "ParkingSegmentName": {"Zh_tw": "莒光街"},
            "ParkingSegmentPosition": {"PositionLat": 22.62, "PositionLon": 120.28},
            "FareDescription": "半時計15",
        }
    ]
    live = [{"ParkingSegmentID": "440", "AvailableSpaces": 6}]
    (curb,) = parse_curbs(segments, live)
    assert (curb.name, curb.fare, curb.free_spaces) == ("莒光街", "$15/半時", 6)


def test_nearest_place_with_space_wins_over_a_nearer_full_one():
    catalog = ParkingCatalog(
        lots=[place("滿的", NEAR, 0), place("有位", FARTHER, 8)],
        curbs=[place("太遠", TOO_FAR, 5)],
        as_of="10:50",
    )
    nearby = catalog.near(SHOP)
    assert nearby.lot.place.name == "有位"
    assert nearby.curb is None


def test_full_places_are_still_shown_when_nothing_nearby_has_space():
    catalog = ParkingCatalog(lots=[place("滿的", NEAR, 0)], curbs=[], as_of="10:50")
    assert catalog.near(SHOP).lot.place.name == "滿的"


def test_parking_line_lists_lot_and_curb_or_says_none_found():
    lot = ParkingOption(place("合發停車場", NEAR, 136), 110)
    curb = ParkingOption(place("大同二路", NEAR, 0), 281)
    assert parking_line(NearbyParking(lot, curb)) == (
        "🅿️ 合發停車場 110m · $15/半時 · 剩 136 格｜路邊 大同二路 281m · $15/半時 · 已滿"
    )
    assert parking_line(NearbyParking(None, None)) == "🅿️ 附近 300m 內查不到停車場"
