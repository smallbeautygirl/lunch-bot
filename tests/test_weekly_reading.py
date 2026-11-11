from __future__ import annotations

from datetime import date
from pathlib import Path

from lunch_bot.horoscope import SignFortune
from lunch_bot.morning_card import build_morning_card
from lunch_bot.weekly_reading import find_reading

# Trimmed copy of the real 唐陽雞酒屋 feed: the 11/9 and 11/2 weekly episodes
# with two ordinary episodes between them.
FEED = (Path(__file__).parent / "fixtures" / "tang_weekly_feed.xml").read_bytes()


def test_reading_covering_the_day_is_the_one_used():
    reading = find_reading(FEED, date(2026, 11, 11))
    assert reading is not None
    assert (reading.start, reading.end) == (date(2026, 11, 9), date(2026, 11, 15))
    assert reading.theme == "不滿情緒容易爆發，先別急著攤牌"
    assert reading.url.startswith("https://open.firstory.fm/story/")


def test_every_sign_gets_its_tier_and_note():
    reading = find_reading(FEED, date(2026, 11, 11))
    assert len(reading.signs) == 12
    assert reading.signs["牡羊座"].tier == "累的"
    assert reading.signs["天秤座"].note == "海外拓展先布局，感情先保持距離"
    # The feed spells it 魔羯.
    assert reading.signs["摩羯座"].tier == "讚的"


def test_last_weeks_episode_covers_last_week():
    reading = find_reading(FEED, date(2026, 11, 5))
    assert reading.start == date(2026, 11, 2)
    assert reading.signs["牡羊座"].note == "工作遇轉折關鍵，感情問題需治療"


def test_no_reading_before_the_weeks_episode_is_out():
    assert find_reading(FEED, date(2026, 11, 16)) is None


def test_morning_card_shows_weekly_tier_and_credits_the_source():
    reading = find_reading(FEED, date(2026, 11, 11))
    fortune = SignFortune(sign="牡羊座", overall="…", wealth_stars=2, lucky_color="藍")
    card = build_morning_card(
        day=date(2026, 11, 11),
        taiex=None,
        overseas=[],
        fortunes=[fortune],
        members={},
        reading=reading,
    )
    texts = " ".join(b["text"] for b in card["attachments"][0]["content"]["body"])
    assert "牡羊座**（本週：累的）" in texts
    assert "唐綺陽星座週報" in texts and reading.url in texts
