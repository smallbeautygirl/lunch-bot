from __future__ import annotations

from datetime import date
from pathlib import Path

from lunch_bot.horoscope import SignFortune, tidy_fortunes
from lunch_bot.mafalda import (
    MafaldaReading,
    MafaldaSign,
    MafaldaTier,
    find_articles,
    parse_opening,
    parse_standings,
)
from lunch_bot.morning_card import HoroscopeContext, build_morning_card
from lunch_bot.sign_sources import SignSources, collect_sources
from lunch_bot.weekly_reading import SignReading, find_reading

FIXTURES = Path(__file__).parent / "fixtures"
# Structure-only excerpts of real LINE TODAY pages (the text is cut short).
LISTING = (FIXTURES / "mafalda_listing.html").read_text()
CALM_WEEK = (FIXTURES / "mafalda_aries_1104.html").read_text()
ROUGH_WEEK = (FIXTURES / "mafalda_aries_slipping.html").read_text()
TANG_FEED = (FIXTURES / "tang_weekly_feed.xml").read_bytes()


def sources(tang: str | None, mafalda: MafaldaTier | None) -> SignSources:
    return SignSources(
        tang=SignReading(tier=tang, note="…") if tang else None,
        mafalda=MafaldaSign(opening="…", url="u", tier=mafalda) if mafalda else None,
    )


def test_listing_picks_the_article_for_the_week_covering_the_day():
    articles = find_articles(LISTING, date(2026, 11, 6))
    assert set(articles) == {"牡羊座", "金牛座", "摩羯座"}
    assert articles["牡羊座"].url.startswith("https://today.line.me/tw/v3/article/")
    assert articles["牡羊座"].week_label == "11/4–11/10"


def test_listing_has_nothing_once_the_week_has_passed():
    assert find_articles(LISTING, date(2026, 11, 11)) == {}


def test_opening_paragraph_is_the_signs_own_text():
    assert parse_opening(CALM_WEEK) == "苦後回甘，倒吃甘蔗。"


def test_ranked_signs_are_top_and_the_rest_normal_in_a_calm_week():
    tiers = parse_standings(CALM_WEEK)
    assert tiers["雙子座"] is MafaldaTier.TOP
    assert tiers["牡羊座"] is MafaldaTier.NORMAL


def test_named_signs_are_slipping_and_double_listed_ones_get_no_tier():
    tiers = parse_standings(ROUGH_WEEK)
    assert tiers["牡羊座"] is MafaldaTier.SLIPPING
    assert tiers["金牛座"] is MafaldaTier.TOP
    assert "天蠍座" not in tiers  # both ranked and named as slipping


def test_unreadable_ranking_gives_no_tiers():
    assert parse_standings("<article><p>…</p></article>") is None


def test_only_opposite_verdicts_clash():
    assert sources("累的", MafaldaTier.TOP).is_clash
    assert sources("讚的", MafaldaTier.SLIPPING).is_clash
    assert not sources("穩的", MafaldaTier.TOP).is_clash
    assert not sources("累的", None).is_clash


def test_stars_stay_where_sources_overlap_or_between_them_on_a_clash():
    assert sources("讚的", MafaldaTier.TOP).star_range == (4, 5)
    assert sources("累的", MafaldaTier.NORMAL).star_range == (2, 2)
    assert sources("累的", MafaldaTier.TOP).star_range == (2, 4)
    assert sources(None, None).star_range == (1, 5)


def test_tidy_clamps_stars_and_drops_invented_conflicts():
    by_sign = {
        "牡羊座": sources("累的", MafaldaTier.TOP),
        "金牛座": sources("讚的", MafaldaTier.TOP),
    }
    fortunes = [
        SignFortune(
            sign="牡羊座",
            overall="…",
            wealth_stars=5,
            lucky_color="紅",
            conflict_note="唐說累、瑪法達說旺",
        ),
        SignFortune(
            sign="金牛座",
            overall="…",
            wealth_stars=1,
            lucky_color="綠",
            conflict_note="其實沒衝突",
        ),
    ]
    aries, taurus = tidy_fortunes(fortunes, list(by_sign), by_sign)
    assert (aries.wealth_stars, aries.conflict_note) == (4, "唐說累、瑪法達說旺")
    assert (taurus.wealth_stars, taurus.conflict_note) == (4, "")


def test_card_labels_both_sources_shows_the_clash_and_credits_both():
    tang = find_reading(TANG_FEED, date(2026, 11, 11))
    mafalda = MafaldaReading(
        week_label="11/11–11/17",
        signs={"牡羊座": MafaldaSign("…", "u", MafaldaTier.TOP)},
    )
    by_sign = collect_sources(["牡羊座"], tang, mafalda)
    fortune = SignFortune(
        sign="牡羊座",
        overall="…",
        wealth_stars=3,
        lucky_color="藍",
        conflict_note="唐老師說累，瑪法達說旺",
    )
    card = build_morning_card(
        day=date(2026, 11, 11),
        taiex=None,
        overseas=[],
        fortunes=[fortune],
        context=HoroscopeContext(sources=by_sign, tang=tang, mafalda=mafalda),
    )
    texts = " ".join(b["text"] for b in card["attachments"][0]["content"]["body"])
    assert "牡羊座**（唐：累的｜瑪法達：前段班）" in texts
    assert "⚖️ 兩派說法不同：唐老師說累，瑪法達說旺" in texts
    assert tang.url in texts and "瑪法達星座運勢" in texts
