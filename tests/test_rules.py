from __future__ import annotations

import random
from datetime import date

from lunch_bot.calendar_tw import DayKind, classify_day
from lunch_bot.card import build_holiday_card, build_workday_card, market_line
from lunch_bot.content import DailyContent, EnglishLesson, ExtraKind, Joke, extras_for
from lunch_bot.history import has_posted_on, recent_shop_ids
from lunch_bot.market import Mood, StockQuote, fits_market, market_factor
from lunch_bot.picker import Candidate, find_candidates, is_open_at, pick_suggestions
from lunch_bot.teams import add_note, mark_as_test
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


def taiex(pct: float, as_of: str = "11/5 收盤") -> StockQuote:
    return StockQuote("加權指數", 100 + pct, 100, as_of)


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


def test_first_suggestion_always_matches_the_fortune():
    candidates = [
        Candidate(make_shop(f"{cat}{i}", cat), Travel(TravelMode.WALK, 5))
        for cat in ("麵", "飯", "日式", "小吃")
        for i in range(10)
    ] + [Candidate(make_shop("ramen", "拉麵"), Travel(TravelMode.WALK, 5))]
    for seed in range(20):
        picks = pick_suggestions(candidates, {"拉麵"}, random.Random(seed))
        assert picks[0].shop["id"] == "ramen"


def test_suggestions_still_filled_when_no_shop_matches_the_fortune():
    candidates = [
        Candidate(make_shop(f"{cat}", cat), Travel(TravelMode.WALK, 5))
        for cat in ("麵", "飯", "日式")
    ]
    assert len(pick_suggestions(candidates, {"拉麵"}, random.Random(1))) == 3


def test_joke_is_labelled_and_split_into_question_and_answer():
    content = DailyContent(joke=Joke(question="什麼動物最愛睡?", answer="無尾熊"))
    card = build_workday_card(
        day=FRIDAY,
        sign="獅子座",
        content=content,
        picks=[],
        chief=None,
        cached_on=None,
    )
    texts = [b["text"] for b in card["attachments"][0]["content"]["body"]]
    assert any(
        "今日小單元：😂 笑話" in t and "Q：" in t and "A：無尾熊" in t for t in texts
    )


def test_test_runs_are_marked_in_the_title():
    card = build_holiday_card(day=FRIDAY, content=DailyContent())
    title = mark_as_test(card)["attachments"][0]["content"]["body"][0]["text"]
    assert title.startswith("[測試中]")


def test_market_mood_follows_the_site_thresholds():
    assert taiex(0.3).mood is Mood.UP
    assert taiex(-4.07).mood is Mood.DOWN
    assert taiex(0.29).mood is Mood.FLAT


def test_market_drop_favours_cheap_shops_and_penalises_fancy_ones():
    drop = taiex(-4.07)
    assert market_factor(make_shop("bento", "便當", price=1), drop) == 2.2
    assert market_factor(make_shop("steak", "牛排", price=3), drop) == 0.4
    assert market_factor(make_shop("hotpot", "火鍋", price=None), drop) == 0.4


def test_missing_quote_leaves_weights_untouched():
    assert market_factor(make_shop("steak", "牛排", price=3), None) == 1.0


def test_market_line_shows_change_timestamp_and_mood():
    line = market_line(taiex(-4.072, "截至 11:05"))
    assert "-4.07%" in line and "截至 11:05" in line and "省一點" in line


def test_lucky_sign_lists_the_members_born_under_it():
    card = build_workday_card(
        day=FRIDAY,
        sign="牡羊座",
        content=DailyContent(fortune="衝就對了"),
        picks=[],
        chief=None,
        cached_on=None,
        sign_members=["amy", "bob"],
    )
    texts = [b["text"] for b in card["attachments"][0]["content"]["body"]]
    assert any("今日幸運星座：牡羊座**（amy、bob）" in t for t in texts)


def test_market_drop_tilts_weighted_pick_towards_cheap_shops():
    cheap = [
        Candidate(make_shop(f"c{i}", f"便當{i}", price=1), Travel(TravelMode.WALK, 5))
        for i in range(5)
    ]
    fancy = [
        Candidate(make_shop(f"f{i}", f"牛排{i}", price=3), Travel(TravelMode.WALK, 5))
        for i in range(5)
    ]
    drop = taiex(-4.07)
    first_picks = [
        pick_suggestions(cheap + fancy, set(), random.Random(seed), drop)[0]
        for seed in range(200)
    ]
    cheap_share = sum(p.shop["price"] == 1 for p in first_picks) / len(first_picks)
    assert cheap_share > 0.75


def test_today_counts_as_posted_only_once_its_entry_is_saved():
    history = [{"date": "2026-11-05", "shop_ids": ["a"]}]
    assert not has_posted_on(history, FRIDAY)
    assert has_posted_on([*history, {"date": "2026-11-06", "shop_ids": []}], FRIDAY)


def walkable(shop: dict) -> Candidate:
    return Candidate(shop, Travel(TravelMode.WALK, 5))


def test_splurge_day_suggests_only_two_dollar_signs_and_up():
    cheap = [walkable(make_shop(f"c{i}", f"小吃{i}", price=1)) for i in range(30)]
    pricey = [
        walkable(make_shop(f"p{i}", f"義式{i}", price=2 + i % 2)) for i in range(5)
    ]
    for seed in range(30):
        picks = pick_suggestions(cheap + pricey, set(), random.Random(seed), taiex(5.9))
        assert all(p.shop["price"] >= 2 for p in picks)


def test_saving_day_suggests_only_one_dollar_sign():
    cheap = [walkable(make_shop(f"c{i}", f"小吃{i}", price=1)) for i in range(5)]
    pricey = [walkable(make_shop(f"p{i}", f"義式{i}", price=3)) for i in range(30)]
    for seed in range(30):
        picks = pick_suggestions(cheap + pricey, set(), random.Random(seed), taiex(-4))
        assert all(p.shop["price"] == 1 for p in picks)


def test_market_filter_tops_up_when_too_few_shops_fit():
    cheap = [walkable(make_shop(f"c{i}", f"小吃{i}", price=1)) for i in range(5)]
    pricey = [walkable(make_shop("p0", "牛排", price=3))]
    picks = pick_suggestions(cheap + pricey, set(), random.Random(1), taiex(5.9))
    assert len(picks) == 3 and picks[0].shop["id"] == "p0"


def test_unpriced_shop_follows_its_category_on_market_days():
    hotpot = make_shop("h", "火鍋", price=None)
    assert fits_market(hotpot, taiex(5.9)) and not fits_market(hotpot, taiex(-4))


def test_joke_shows_its_punchline_explanation():
    joke = Joke(question="哪種花最沒力？", answer="茉莉花", explanation="台語諧音")
    card = build_workday_card(
        day=FRIDAY,
        sign="獅子座",
        content=DailyContent(joke=joke),
        picks=[],
        chief=None,
        cached_on=None,
    )
    texts = [b["text"] for b in card["attachments"][0]["content"]["body"]]
    assert any("笑點解析：台語諧音" in t for t in texts)


def test_english_lesson_shows_its_homophone_mnemonic():
    lesson = EnglishLesson(
        word="kangaroo",
        meaning="袋鼠",
        mnemonic="袋鼠跳太快，每跳一下都要停下來「看個路」。",
        sentence="A kangaroo can't walk backwards.",
        translation="袋鼠不能倒著走。",
    )
    card = build_workday_card(
        day=FRIDAY,
        sign="獅子座",
        content=DailyContent(english=lesson),
        picks=[],
        chief=None,
        cached_on=None,
    )
    texts = " ".join(b["text"] for b in card["attachments"][0]["content"]["body"])
    assert "**kangaroo**：袋鼠" in texts and "「看個路」" in texts


def test_note_appears_right_under_the_title():
    card = build_holiday_card(day=date(2026, 10, 10), content=DailyContent())
    body = add_note(card, "運勢改參考週報")["attachments"][0]["content"]["body"]
    assert body[1]["text"] == "📣 運勢改參考週報"


def test_unparseable_claude_reply_gives_no_content_instead_of_crashing(monkeypatch):
    from pydantic import BaseModel

    from lunch_bot import claude

    class Reply(BaseModel):
        text: str

    def cut_off_reply(**_kwargs):
        Reply.model_validate_json('{"text": "cut')

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    client = claude.anthropic.Anthropic()
    monkeypatch.setattr(client.messages, "parse", cut_off_reply)
    monkeypatch.setattr(claude.anthropic, "Anthropic", lambda: client)
    assert claude.ask_claude("prompt", Reply) is None
