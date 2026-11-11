from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .horoscope import SignFortune, luckiest_signs
from .mafalda import PUBLISHER_URL, MafaldaReading
from .mafalda import SOURCE_NAME as MAFALDA_SOURCE_NAME
from .market import StockQuote
from .sign_sources import MAX_STARS, SignSources
from .teams import open_url_action, text_block, wrap_card
from .weekly_reading import SOURCE_NAME as TANG_SOURCE_NAME
from .weekly_reading import WeeklyReading
from .zodiac import SIGN_SYMBOLS

WEEKDAY_NAMES = "一二三四五六日"
LIVE_TAIEX_URL = "https://tw.stock.yahoo.com/quote/%5ETWII"
DISCLAIMER = "運勢由 AI 產生，僅供娛樂；股市資訊非投資建議。"


@dataclass(frozen=True)
class HoroscopeContext:
    members: dict[str, list[str]] = field(default_factory=dict)
    sources: dict[str, SignSources] = field(default_factory=dict)
    tang: WeeklyReading | None = None
    mafalda: MafaldaReading | None = None


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


def _source_labels(sources: SignSources | None) -> str:
    if sources is None:
        return ""
    labels = []
    if sources.tang:
        labels.append(f"唐：{sources.tang.tier}")
    if sources.mafalda:
        labels.append(f"瑪法達：{sources.mafalda_tier or '—'}")
    return f"（{'｜'.join(labels)}）" if labels else ""


def _fortune_blocks(
    fortune: SignFortune, names: list[str], sources: SignSources | None
) -> list[dict]:
    heading = f"**{SIGN_SYMBOLS[fortune.sign]} {fortune.sign}**"
    heading += _source_labels(sources)
    if names:
        heading += f"　{'、'.join(names)}"
    facts = f"財運 {_stars(fortune.wealth_stars)} · 幸運色：{fortune.lucky_color}"
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


def _horoscope_blocks(
    fortunes: list[SignFortune], context: HoroscopeContext
) -> list[dict]:
    blocks = [text_block("**🔮 今日星座運勢**", separator=True)]
    if not fortunes:
        return [*blocks, text_block("今天的運勢暫時算不出來 🙏")]
    for fortune in fortunes:
        names = context.members.get(fortune.sign, [])
        blocks += _fortune_blocks(fortune, names, context.sources.get(fortune.sign))
    luckiest = "、".join(luckiest_signs(fortunes))
    blocks.append(text_block(f"💰 **今日財運最旺：{luckiest}**", spacing="Medium"))
    if credits := _credit_lines(context.tang, context.mafalda):
        blocks.append(
            text_block(
                "參考：\n\n" + "\n\n".join(credits),
                isSubtle=True,
                size="Small",
                spacing="Medium",
            )
        )
    return blocks


def build_morning_card(
    *,
    day: date,
    taiex: StockQuote | None,
    overseas: list[StockQuote],
    fortunes: list[SignFortune],
    context: HoroscopeContext,
    almanac: list[str] | None = None,
) -> dict:
    title = f"☀️ 早安！{day.month}/{day.day}（{WEEKDAY_NAMES[day.weekday()]}）"
    body = [text_block(title, size="Large", weight="Bolder")]
    body += _market_blocks(taiex, overseas)
    if almanac:
        body.append(text_block("\n\n".join(almanac), separator=True))
    body += _horoscope_blocks(fortunes, context)
    body.append(text_block(DISCLAIMER, isSubtle=True, size="Small", separator=True))
    return wrap_card(body, actions=[open_url_action("看即時盤", LIVE_TAIEX_URL)])
