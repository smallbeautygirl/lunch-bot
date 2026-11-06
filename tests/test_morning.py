from __future__ import annotations

from datetime import date

from lunch_bot.horoscope import SignFortune, luckiest_signs, tidy_fortunes
from lunch_bot.market import StockQuote
from lunch_bot.morning_card import build_morning_card, stock_line
from lunch_bot.stocks import parse_chart
from lunch_bot.zodiac import parse_members

MONDAY = date(2026, 11, 9)
TAIPEI_OFFSET = 28800
# 2026-11-06 09:00 → 13:30 Asia/Taipei
OPEN, CLOSE = 1793926800, 1793943000


def chart_meta(traded_at: int) -> dict:
    return {
        "regularMarketPrice": 39701.64,
        "chartPreviousClose": 42948.9,
        "regularMarketTime": traded_at,
        "gmtoffset": TAIPEI_OFFSET,
        "currentTradingPeriod": {"regular": {"start": OPEN, "end": CLOSE}},
    }


def fortune(sign: str, stars: int) -> SignFortune:
    return SignFortune(
        sign=sign, overall="順順的", wealth_stars=stars, lucky_color="紅"
    )


def card_texts(card: dict) -> list[str]:
    return [block["text"] for block in card["attachments"][0]["content"]["body"]]


def test_quote_during_trading_is_stamped_with_its_time():
    quote = parse_chart(chart_meta(OPEN + 14 * 60), "加權指數")
    assert quote.as_of == "截至 09:14"
    assert round(quote.pct, 2) == -7.56


def test_quote_before_the_open_is_labelled_as_previous_close():
    yesterday_close = OPEN - 20 * 3600
    assert parse_chart(chart_meta(yesterday_close), "加權指數").as_of == "11/5 收盤"


def test_quote_after_the_close_is_labelled_as_todays_close():
    assert parse_chart(chart_meta(CLOSE + 195), "加權指數").as_of == "11/6 收盤"


def test_chart_without_a_price_yields_no_quote():
    assert parse_chart({"chartPreviousClose": 1.0}, "加權指數") is None


def test_members_accept_short_sign_names_and_follow_zodiac_order():
    members = parse_members({"水瓶": ["a"], "牡羊座": ["b"], "牡羊": ["c"]})
    assert members == {"牡羊座": ["b", "c"], "水瓶座": ["a"]}


def test_members_with_unknown_signs_are_dropped():
    assert parse_members({"貓咪座": ["a"], "雙魚": "not-a-list"}) == {}


def test_fortunes_keep_one_per_requested_sign_with_stars_in_range():
    tidied = tidy_fortunes(
        [fortune("雙魚座", 9), fortune("牡羊座", 0), fortune("牡羊座", 3)],
        ["牡羊座", "雙魚座"],
    )
    assert [(f.sign, f.wealth_stars) for f in tidied] == [("牡羊座", 1), ("雙魚座", 5)]


def test_fortunes_for_signs_nobody_asked_for_are_dropped():
    assert tidy_fortunes([fortune("巨蟹座", 3)], ["牡羊座"]) == []


def test_every_sign_tied_for_top_wealth_is_named():
    fortunes = [fortune("牡羊座", 4), fortune("獅子座", 4), fortune("天秤座", 2)]
    assert luckiest_signs(fortunes) == ["牡羊座", "獅子座"]


def test_stock_line_shows_price_change_and_timestamp():
    line = stock_line(StockQuote("加權指數", 39701.64, 42948.9, "截至 09:14"))
    assert line == "📉 **加權指數** 39,701.64（-7.56%）截至 09:14"


def test_morning_card_lists_names_stars_luckiest_sign_and_disclaimer():
    card = build_morning_card(
        day=MONDAY,
        taiex=StockQuote("加權指數", 101, 100, "截至 09:05"),
        overseas=[],
        fortunes=[fortune("牡羊座", 4), fortune("獅子座", 2)],
        members={"牡羊座": ["amy", "bob"]},
    )
    texts = "\n".join(card_texts(card))
    assert "♈ 牡羊座**　amy、bob" in texts
    assert "財運 ★★★★☆" in texts
    assert "今日財運最旺：牡羊座" in texts
    assert "非投資建議" in texts
    actions = card["attachments"][0]["content"]["actions"]
    assert actions[0]["title"] == "看即時盤"


def test_morning_card_still_posts_when_market_and_horoscope_fail():
    card = build_morning_card(
        day=MONDAY, taiex=None, overseas=[], fortunes=[], members={}
    )
    texts = "\n".join(card_texts(card))
    assert "股市資料暫時抓不到" in texts and "運勢暫時算不出來" in texts
