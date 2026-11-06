from __future__ import annotations

import random
from datetime import date

from lunch_bot.calendar_tw import DayKind, classify_day
from lunch_bot.card import build_workday_card
from lunch_bot.content import DailyContent, ExtraKind, extras_for
from lunch_bot.history import recent_shop_ids
from lunch_bot.picker import Candidate, find_candidates, is_open_at, pick_suggestions
from lunch_bot.travel import Travel, TravelMode, estimate_travel

FRIDAY = date(2026, 11, 6)
SATURDAY = date(2026, 11, 7)
SETTINGS = {
    "office": {"lat": 22.6184, "lng": 120.2782},
    "depart": {"start": "11:40"},
    "walkSpeed": 80,
    "detour": 1.25,
    "maxWalkMin": 10,
    "driveSpeed": 400,
    "parkSearch": 3,
    "streetSearch": 6,
    "driveWorthIt": 5,
    "maxDriveMin": 15,
}
LUNCH_HOURS = {
    key: [["11:00", "14:00"]]
    for key in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
}


def make_shop(shop_id: str, category: str, **overrides: object) -> dict:
    shop = {
        "id": shop_id,
        "name": shop_id,
        "lat": 22.6190,
        "lng": 120.2790,
        "category": [category],
        "price": 1,
        "service": ["dine_in"],
        "hours": LUNCH_HOURS,
        "hoursUnknown": False,
        "needsReview": False,
    }
    return {**shop, **overrides}


def test_weekday_without_calendar_data_is_workday():
    assert classify_day(FRIDAY, None) is DayKind.WORKDAY


def test_weekday_marked_holiday_is_national_holiday():
    assert classify_day(FRIDAY, {"20261106": True}) is DayKind.NATIONAL_HOLIDAY


def test_saturday_marked_workday_is_makeup_workday():
    assert classify_day(SATURDAY, {"20261107": False}) is DayKind.WORKDAY


def test_ordinary_saturday_is_weekend():
    assert classify_day(SATURDAY, {"20261107": True}) is DayKind.WEEKEND


def test_shop_open_past_midnight_counts_as_open_at_lunch():
    shop = make_shop("bbq", "燒肉", hours={"fri": [["11:30", "00:00"]]})
    assert is_open_at(shop, FRIDAY, "11:40")


def test_shop_with_unknown_hours_is_not_suggested():
    assert not is_open_at(make_shop("x", "麵", hoursUnknown=True), FRIDAY, "11:40")


def test_nearby_shop_is_walkable():
    travel = estimate_travel(make_shop("near", "麵"), [], SETTINGS)
    assert travel is not None and travel.mode is TravelMode.WALK


def test_shop_2km_away_needs_a_car():
    travel = estimate_travel(make_shop("far", "麵", lat=22.6350), [], SETTINGS)
    assert travel is not None and travel.mode is TravelMode.DRIVE


def test_shop_beyond_drive_limit_is_unreachable():
    assert estimate_travel(make_shop("x", "麵", lat=22.75), [], SETTINGS) is None


def test_expensive_delivery_only_and_recent_shops_are_filtered_out():
    shops = [
        make_shop("ok", "麵"),
        make_shop("pricey", "牛排", price=4),
        make_shop("delivery", "披薩", service=["delivery"]),
        make_shop("recent", "飯"),
    ]
    found = find_candidates(shops, [], SETTINGS, day=FRIDAY, excluded={"recent"})
    assert [c.shop["id"] for c in found] == ["ok"]


def test_recent_ids_cover_last_five_days_excluding_today():
    oldest = {"date": "2026-10-31", "shop_ids": ["too-old"]}
    history = [oldest] + [
        {"date": f"2026-11-0{d}", "shop_ids": [f"s{d}"]} for d in range(1, 7)
    ]
    assert recent_shop_ids(history, FRIDAY) == {"s1", "s2", "s3", "s4", "s5"}


def test_suggestions_are_three_distinct_categories_and_reproducible():
    candidates = [
        Candidate(make_shop(f"{cat}{i}", cat), Travel(TravelMode.WALK, 5))
        for cat in ("麵", "飯", "火鍋", "日式")
        for i in range(3)
    ]
    first = pick_suggestions(candidates, {"火鍋"}, random.Random("2026-11-06"))
    again = pick_suggestions(candidates, {"火鍋"}, random.Random("2026-11-06"))
    assert [c.shop["id"] for c in first] == [c.shop["id"] for c in again]
    assert len({c.shop["category"][0] for c in first}) == 3


def test_holiday_gets_english_and_joke():
    assert extras_for(FRIDAY, DayKind.NATIONAL_HOLIDAY) == [
        ExtraKind.ENGLISH,
        ExtraKind.JOKE,
    ]


def test_workday_card_mentions_chief_through_teams_entity():
    card = build_workday_card(
        day=FRIDAY,
        sign="獅子座",
        content=DailyContent(),
        picks=[],
        chief=("chief@example.com", "Chief"),
        cached_on=None,
    )
    content = card["attachments"][0]["content"]
    entity = content["msteams"]["entities"][0]
    assert entity["mentioned"]["id"] == "chief@example.com"
    assert any("<at>Chief</at>" in block["text"] for block in content["body"])
