from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .horoscope import SignFortune, luckiest_signs
from .mafalda import PUBLISHER_URL, MafaldaReading
from .mafalda import SOURCE_NAME as MAFALDA_SOURCE_NAME
from .market import StockQuote
from .sign_sources import MAX_STARS
from .teams import container, open_url_action, text_block, toggle_action, wrap_card
from .weekly_reading import SOURCE_NAME as TANG_SOURCE_NAME
from .weekly_reading import WeeklyReading
from .zodiac import SIGN_SYMBOLS

WEEKDAY_NAMES = "一二三四五六日"
LIVE_TAIEX_URL = "https://tw.stock.yahoo.com/quote/%5ETWII"
DISCLAIMER = "運勢由 AI 產生，僅供娛樂；股市資訊非投資建議。"
HOROSCOPE_ID = "horoscope"


@dataclass(frozen=True)
class HoroscopeContext:
    members: dict[str, list[str]] = field(default_factory=dict)
    tang: WeeklyReading | None = None
    mafalda: MafaldaReading | None = None


def stock_line(quote: StockQuote) -> str:
    arrow = "📈" if quote.pct >= 0 else "📉"
    change = f"{quote.price:,.2f}（{quote.pct:+.2f}%）"
    return f"{arrow} **{quote.linked_name}** {change}{quote.as_of}"


def _change(quote: StockQuote) -> str:
    arrow = "▲" if quote.pct >= 0 else "▼"
    return f"{quote.linked_name} {arrow}{abs(quote.pct):.2f}%"


def _market_block(taiex: StockQuote | None, overseas: list[StockQuote]) -> dict:
    """One line of changes; prices and timestamps are a tap away on 看即時盤."""
    quotes = [quote for quote in [taiex, *overseas] if quote]
    if not quotes:
        return text_block("📊 今天股市資料暫時抓不到 🙏")
    return text_block("📊 " + " · ".join(_change(quote) for quote in quotes))


def _section(lines: list[str]) -> dict:
    """A shaded box, so the card reads as a few blocks instead of one wall."""
    blocks = [
        text_block(lines[0]),
        *(text_block(line, spacing="Small") for line in lines[1:]),
    ]
    return container(blocks, style="emphasis", spacing="Medium")


def _stars(count: int) -> str:
    return "★" * count + "☆" * (MAX_STARS - count)


def _fortune_blocks(fortune: SignFortune, names: list[str]) -> list[dict]:
    heading = f"**{SIGN_SYMBOLS[fortune.sign]} {fortune.sign}**"
    if names:
        heading += f"　{'、'.join(names)}"
    wealth = f"財運 {_stars(fortune.wealth_stars)}"
    if fortune.wealth_note:
        wealth += f"　{fortune.wealth_note}"
    facts = f"{wealth} · 幸運色：{fortune.lucky_color}"
    blocks = [
        text_block(heading, spacing="Medium"),
        text_block(fortune.overall, spacing="None"),
    ]
    if fortune.conflict_note:
        blocks.append(
            text_block(f"⚖️ 兩派說法不同：{fortune.conflict_note}", spacing="Small")
        )
    return [*blocks, text_block(facts, isSubtle=True, spacing="None")]


def _credit_lines(
    tang: WeeklyReading | None, mafalda: MafaldaReading | None
) -> list[str]:
    lines = []
    if tang:
        lines.append(
            f"📻 [{TANG_SOURCE_NAME}]({tang.url}) {tang.week_label}：{tang.theme}"
        )
    if mafalda:
        lines.append(
            f"📰 [{MAFALDA_SOURCE_NAME}]({PUBLISHER_URL}) {mafalda.week_label}"
        )
    return lines


def _horoscope_details(fortunes: list[SignFortune], context: HoroscopeContext) -> dict:
    """Every sign's fortune, hidden until 星座運勢 is tapped: at seven signs
    it is most of the card's length."""
    blocks: list[dict] = []
    for fortune in fortunes:
        blocks += _fortune_blocks(fortune, context.members.get(fortune.sign, []))
    if credits := _credit_lines(context.tang, context.mafalda):
        blocks.append(
            text_block(
                "參考：\n\n" + "\n\n".join(credits),
                isSubtle=True,
                size="Small",
                spacing="Medium",
            )
        )
    return container(blocks, id=HOROSCOPE_ID, isVisible=False)


def build_morning_card(
    *,
    day: date,
    taiex: StockQuote | None,
    overseas: list[StockQuote],
    fortunes: list[SignFortune],
    context: HoroscopeContext,
    group_sections: list[list[str]] | None = None,
) -> dict:
    title = f"☀️ 早安！{day.month}/{day.day}（{WEEKDAY_NAMES[day.weekday()]}）"
    body = [text_block(title, size="Large", weight="Bolder")]
    body.append(_market_block(taiex, overseas))
    body += [_section(lines) for lines in group_sections or []]
    actions = [open_url_action("看即時盤", LIVE_TAIEX_URL)]
    if fortunes:
        luckiest = "、".join(luckiest_signs(fortunes))
        body.append(text_block(f"🔮 **今日財運最旺：{luckiest}**", spacing="Medium"))
        body.append(_horoscope_details(fortunes, context))
        actions.insert(0, toggle_action("星座運勢 展開／收起", HOROSCOPE_ID))
    else:
        body.append(text_block("🔮 今天的運勢暫時算不出來 🙏", spacing="Medium"))
    body.append(text_block(DISCLAIMER, isSubtle=True, size="Small", separator=True))
    return wrap_card(body, actions=actions)
