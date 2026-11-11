from __future__ import annotations

from datetime import date

from lunch_bot.almanac import Almanac, almanac_lines, compute_almanac

ALMANAC = Almanac(
    lunar_date="十月初六", clash_animal="狗", good=["祭祀", "理髮"], bad=["動土"]
)


def test_almanac_is_the_real_lunar_day_in_traditional_chinese():
    almanac = compute_almanac(date(2026, 11, 14))
    assert almanac.lunar_date == "十月初六"
    assert almanac.clash_animal == "狗"
    assert almanac.good == ["祭祀", "理髮", "針灸"]
    assert almanac.bad == ["嫁娶", "動土"]


def test_each_term_gets_its_workplace_reading():
    lines = almanac_lines(ALMANAC, {"祭祀": "對 GPU 機房拜拜", "動土": "重構舊程式"})
    assert lines == [
        "📅 **職場農民曆**　農曆十月初六 · 沖狗",
        "✅ 宜：祭祀（對 GPU 機房拜拜）、理髮",
        "⛔ 忌：動土（重構舊程式）",
    ]


def test_plain_terms_are_shown_when_claude_has_nothing():
    assert almanac_lines(ALMANAC, {})[1] == "✅ 宜：祭祀、理髮"
