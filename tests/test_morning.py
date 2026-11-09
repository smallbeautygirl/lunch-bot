from __future__ import annotations

from datetime import date, datetime, time

from lunch_bot.horoscope import SignFortune, luckiest_signs, tidy_fortunes
from lunch_bot.market import StockQuote
from lunch_bot.morning_card import build_morning_card, stock_line
from lunch_bot.stocks import parse_chart, quote_page_url
from lunch_bot.teams import is_past_deadline
from lunch_bot.zodiac import parse_members

MONDAY = date(2026, 11, 9)
TAIPEI_OFFSET = 28800
# 2026-11-06 09:00 → 13:30 Asia/Taipei
OPEN, CLOSE = 1793926800, 1793943000


DAY = 86400
# Daily bars stamped at the 09:00 open, 11/2 → 11/6; Yahoo leaves today's
# close empty until it settles.
BAR_OPENS = [OPEN - offset * DAY for offset in (4, 3, 2, 1, 0)]
BAR_CLOSES = [44920.14, 43307.54, 42948.91, 41574.72, None]


def chart(traded_at: int, price: float = 39701.64) -> dict:
    return {
        "meta": {
            "regularMarketPrice": price,
            # Stale on purpose: Yahoo has served 11/4's close beside 11/6's price.
            "chartPreviousClose": 42948.9,
            "regularMarketTime": traded_at,
            "gmtoffset": TAIPEI_OFFSET,
            "currentTradingPeriod": {"regular": {"start": OPEN, "end": CLOSE}},
        },
        "timestamp": BAR_OPENS,
        "indicators": {"quote": [{"close": BAR_CLOSES}]},
    }


def fortune(sign: str, stars: int) -> SignFortune:
    return SignFortune(
        sign=sign, overall="順順的", wealth_stars=stars, lucky_color="紅"
    )


def card_texts(card: dict) -> list[str]:
    return [block["text"] for block in card["attachments"][0]["content"]["body"]]


def test_quote_during_trading_is_stamped_with_its_time():
    assert parse_chart(chart(OPEN + 14 * 60), "加權指數").as_of == "截至 09:14"


def test_change_is_against_the_last_close_before_the_quotes_day():
    quote = parse_chart(chart(OPEN + 14 * 60), "加權指數")
    assert quote.previous_close == 41574.72
    assert round(quote.pct, 2) == -4.51


def test_stale_quote_from_yesterday_compares_with_the_day_before():
    yesterday_close = CLOSE - DAY
    quote = parse_chart(chart(yesterday_close, price=41574.72), "加權指數")
    assert quote.as_of == "11/5 收盤"
    assert round(quote.pct, 2) == -3.20


def test_quote_after_the_close_is_labelled_as_todays_close():
    assert parse_chart(chart(CLOSE + 195), "加權指數").as_of == "11/6 收盤"


def test_chart_without_a_price_yields_no_quote():
    assert parse_chart({"meta": {}}, "加權指數") is None


def test_chart_without_an_earlier_close_yields_no_quote():
    bare = chart(OPEN + 60)
    bare["timestamp"], bare["indicators"] = [OPEN], {"quote": [{"close": [1.0]}]}
    assert parse_chart(bare, "加權指數") is None


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


def test_stock_name_links_to_its_quote_page():
    url = quote_page_url("^TWII")
    assert url == "https://tw.stock.yahoo.com/quote/%5ETWII"
    line = stock_line(StockQuote("加權指數", 101, 100, "截至 09:05", url))
    assert f"**[加權指數]({url})**" in line


def test_run_started_past_the_deadline_does_not_post():
    afternoon = datetime(2026, 11, 7, 15, 2)
    assert is_past_deadline(time(10, 30), afternoon)


def test_run_on_time_or_without_deadline_posts():
    on_time = datetime(2026, 11, 9, 9, 27)
    assert not is_past_deadline(time(10, 30), on_time)
    assert not is_past_deadline(None, on_time)
