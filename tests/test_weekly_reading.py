from __future__ import annotations

from datetime import date
from pathlib import Path

from lunch_bot.weekly_reading import find_reading

# The real 唐陽雞酒屋 feed's shape: the 11/9 and 11/2 weekly episodes with two
# ordinary ones between them. Her notes are placeholders, as this repo is public.
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
    assert reading.signs["天秤座"].note == "工作提醒6，感情提醒"
    # The feed spells it 魔羯.
    assert reading.signs["摩羯座"].tier == "讚的"


def test_last_weeks_episode_covers_last_week():
    reading = find_reading(FEED, date(2026, 11, 5))
    assert reading.start == date(2026, 11, 2)
    assert reading.signs["牡羊座"].note == "工作提醒1，感情提醒"


def test_no_reading_before_the_weeks_episode_is_out():
    assert find_reading(FEED, date(2026, 11, 16)) is None
