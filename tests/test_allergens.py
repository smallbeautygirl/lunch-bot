from __future__ import annotations

import json
import random

from lunch_bot.allergens import (
    DISCLAIMER,
    MemberAllergens,
    ensure_safe_pick,
    is_safe_for_all,
    read_member_allergens,
    warnings_for,
)
from lunch_bot.picker import Candidate
from lunch_bot.travel import Travel, TravelMode

LEO = MemberAllergens("Leo", frozenset({"蛋", "奶類"}), frozenset({"小麥"}))
GUESSES = {
    "noodle": ["小麥"],
    "brunch": ["蛋", "奶類", "小麥"],
    "rice": [],
    "mystery": None,
}


def candidate(shop_id: str) -> Candidate:
    shop = {"id": shop_id, "name": shop_id, "category": ["x"], "price": 1}
    return Candidate(shop, Travel(TravelMode.WALK, 5))


def test_allergens_are_read_in_the_fixed_vocabulary(monkeypatch):
    raw = {"Leo": {"severe": ["蛋", "乳酪"], "moderate": ["小麥"]}, "Bo": {}}
    monkeypatch.setenv("MEMBER_ALLERGENS", json.dumps(raw))
    assert read_member_allergens() == [
        MemberAllergens("Leo", frozenset({"蛋"}), frozenset({"小麥"}))
    ]


def test_moderate_allergen_is_warned_about_but_still_counts_as_safe():
    assert is_safe_for_all("noodle", GUESSES, [LEO])
    assert warnings_for("noodle", GUESSES, [LEO]) == ["⚠️ Leo 注意：可能含小麥"]


def test_severe_allergen_makes_a_shop_unsafe_and_lists_every_hit():
    assert not is_safe_for_all("brunch", GUESSES, [LEO])
    assert warnings_for("brunch", GUESSES, [LEO]) == [
        "⚠️ Leo 注意：可能含蛋、奶類、小麥"
    ]


def test_shop_nobody_could_guess_is_neither_safe_nor_warned_about():
    assert not is_safe_for_all("mystery", GUESSES, [LEO])
    assert not is_safe_for_all("never-guessed", GUESSES, [LEO])
    assert warnings_for("mystery", GUESSES, [LEO]) == []


def test_last_pick_gives_way_when_no_pick_is_safe():
    picks = [candidate("brunch"), candidate("mystery")]
    pool = [*picks, candidate("rice")]
    safer = ensure_safe_pick(picks, pool, GUESSES, [LEO], random.Random(1))
    assert [pick.shop["id"] for pick in safer] == ["brunch", "rice"]


def test_picks_stay_when_one_is_already_safe_or_nothing_safer_exists():
    rng = random.Random(1)
    safe_already = [candidate("brunch"), candidate("noodle")]
    assert ensure_safe_pick(safe_already, safe_already, GUESSES, [LEO], rng) == (
        safe_already
    )
    none_safe = [candidate("brunch")]
    assert ensure_safe_pick(none_safe, none_safe, GUESSES, [LEO], rng) == none_safe
    assert ensure_safe_pick(none_safe, none_safe, GUESSES, [], rng) == none_safe


def test_disclaimer_says_the_allergens_are_a_guess():
    assert "推測" in DISCLAIMER
