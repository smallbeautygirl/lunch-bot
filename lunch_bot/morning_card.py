from __future__ import annotations

from datetime import date

from .horoscope import MAX_STARS, SignFortune, luckiest_signs
from .market import StockQuote
from .teams import open_url_action, text_block, wrap_card
from .weekly_reading import SOURCE_NAME, WeeklyReading
from .zodiac import SIGN_SYMBOLS

WEEKDAY_NAMES = "一二三四五六日"
LIVE_TAIEX_URL = "https://tw.stock.yahoo.com/quote/%5ETWII"
DISCLAIMER = "運勢由 AI 產生，僅供娛樂；股市資訊非投資建議。"


def stock_line(quote: StockQuote) -> str:
    arrow = "📈" if quote.pct >= 0 else "📉"
    change = f"{quote.price:,.2f}（{quote.pct:+.2f}%）"
    return f"{arrow} **{quote.linked_name}** {change}{quote.as_of}"


def _market_blocks(taiex: StockQuote | None, overseas: list[StockQuote]) -> list[dict]:
    blocks = [text_block("**📊 股市**", separator=True)]
    if taiex:
        blocks.append(text_block(stock_line(taiex)))
    if overseas:
        lines = "\n\n".join(stock_line(quote) for quote in overseas)
        blocks.append(text_block(f"🌙 隔夜美股\n\n{lines}", spacing="Small"))
    if len(blocks) == 1:
        blocks.append(text_block("今天股市資料暫時抓不到 🙏"))
    return blocks


def _stars(count: int) -> str:
    return "★" * count + "☆" * (MAX_STARS - count)


def _fortune_blocks(
    fortune: SignFortune, names: list[str], weekly_tier: str | None
) -> list[dict]:
    heading = f"**{SIGN_SYMBOLS[fortune.sign]} {fortune.sign}**"
    if weekly_tier:
        heading += f"（本週：{weekly_tier}）"
    if names:
        heading += f"　{'、'.join(names)}"
    facts = f"財運 {_stars(fortune.wealth_stars)} · 幸運色：{fortune.lucky_color}"
    return [
        text_block(heading, spacing="Medium"),
        text_block(fortune.overall, spacing="None"),
        text_block(facts, isSubtle=True, spacing="None"),
    ]


def _weekly_tier(reading: WeeklyReading | None, sign: str) -> str | None:
    if reading is None or sign not in reading.signs:
        return None
    return reading.signs[sign].tier


def _source_block(reading: WeeklyReading) -> dict:
    return text_block(
        f"📻 參考 [{SOURCE_NAME}]({reading.url}) {reading.week_label}：{reading.theme}",
        isSubtle=True,
        size="Small",
        spacing="Medium",
    )


def _horoscope_blocks(
    fortunes: list[SignFortune],
    members: dict[str, list[str]],
    reading: WeeklyReading | None,
) -> list[dict]:
    blocks = [text_block("**🔮 今日星座運勢**", separator=True)]
    if not fortunes:
        return [*blocks, text_block("今天的運勢暫時算不出來 🙏")]
    for fortune in fortunes:
        tier = _weekly_tier(reading, fortune.sign)
        blocks += _fortune_blocks(fortune, members.get(fortune.sign, []), tier)
    luckiest = "、".join(luckiest_signs(fortunes))
    blocks.append(text_block(f"💰 **今日財運最旺：{luckiest}**", spacing="Medium"))
    if reading:
        blocks.append(_source_block(reading))
    return blocks


def build_morning_card(
    *,
    day: date,
    taiex: StockQuote | None,
    overseas: list[StockQuote],
    fortunes: list[SignFortune],
    members: dict[str, list[str]],
    reading: WeeklyReading | None = None,
) -> dict:
    title = f"☀️ 早安！{day.month}/{day.day}（{WEEKDAY_NAMES[day.weekday()]}）"
    body = [text_block(title, size="Large", weight="Bolder")]
    body += _market_blocks(taiex, overseas)
    body += _horoscope_blocks(fortunes, members, reading)
    body.append(text_block(DISCLAIMER, isSubtle=True, size="Small", separator=True))
    return wrap_card(body, actions=[open_url_action("看即時盤", LIVE_TAIEX_URL)])
