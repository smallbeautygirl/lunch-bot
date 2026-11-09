"""Adaptive Card payloads for the Teams Workflow webhook. A real @mention only
notifies when it is declared in msteams.entities — plain "@name" text does not."""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import quote

from .config import LUNCH_MAP_BASE_URL
from .content import DailyContent
from .market import MOOD_LABELS, Mood, StockQuote
from .picker import Candidate
from .teams import open_url_action, text_block, wrap_card
from .travel import TravelMode

WEEKDAY_NAMES = "一二三四五六日"
RATING_IN_NOTE = re.compile(r"Google ([\d.]+)★")
MOOD_RULES = {Mood.UP: "，只推 $$ 以上", Mood.FLAT: "", Mood.DOWN: "，只推 $ 平價"}
TRAVEL_LABELS = {TravelMode.WALK: "🚶 走路", TravelMode.DRIVE: "🚗 開車"}


def _rating(shop: dict) -> str | None:
    if shop.get("googleRating"):
        return str(shop["googleRating"])
    match = RATING_IN_NOTE.search(shop.get("note") or "")
    return match.group(1) if match else None


def _map_url(shop: dict) -> str:
    query = quote(f"{shop['name']} {shop.get('addr') or ''}".strip())
    return f"https://www.google.com/maps/search/?api=1&query={query}"


def _candidate_blocks(index: int, candidate: Candidate) -> list[dict]:
    shop, travel = candidate.shop, candidate.travel
    facts = ["、".join(shop["category"])]
    facts.append("$" * shop["price"] if shop.get("price") else "價位未知")
    if rating := _rating(shop):
        facts.append(f"⭐ {rating}")
    facts.append(f"{TRAVEL_LABELS[travel.mode]} {travel.minutes} 分")
    return [
        text_block(
            f"**{index}. {shop['name']}**　[地圖]({_map_url(shop)})", spacing="Medium"
        ),
        text_block(" · ".join(facts), isSubtle=True, spacing="None"),
    ]


def _segment(label: str, lines: list[str]) -> dict:
    return text_block("\n\n".join([f"**今日小單元：{label}**", *lines]), separator=True)


def _extra_blocks(content: DailyContent) -> list[dict]:
    blocks = []
    if joke := content.joke:
        lines = [f"Q：{joke.question}", f"A：{joke.answer}"]
        if joke.explanation:
            lines.append(f"_💡 笑點：{joke.explanation}_")
        blocks.append(_segment("😂 笑話", lines))
    if lesson := content.english:
        blocks.append(
            _segment(
                "📖 每日一句英文",
                [
                    lesson.sentence,
                    lesson.translation,
                    f"🔑 **{lesson.keyword}**：{lesson.keyword_meaning}",
                ],
            )
        )
    if content.trivia:
        blocks.append(_segment("💡 冷知識", [content.trivia]))
    return blocks


def _lunch_card(body: list[dict], entities: list[dict] | None = None) -> dict:
    actions = [open_url_action("打開午餐地圖", LUNCH_MAP_BASE_URL)]
    return wrap_card(body, actions=actions, entities=entities)


def _chief_blocks(chief: tuple[str, str] | None) -> tuple[list[dict], list[dict]]:
    closing = "今天不在的話，第一個回覆的人決定 🙋"
    if chief is None:
        return [text_block(f"午餐長請拍板！{closing}", separator=True)], []
    email, name = chief
    mention = f"<at>{name}</at>"
    entity = {
        "type": "mention",
        "text": mention,
        "mentioned": {"id": email, "name": name},
    }
    return [text_block(f"{mention} 午餐長請拍板！{closing}", separator=True)], [entity]


def market_line(quote: StockQuote) -> str:
    arrow = "📈" if quote.pct >= 0 else "📉"
    return (
        f"{arrow} **{quote.linked_name} {quote.pct:+.2f}%**（{quote.as_of}）"
        f" → 今天{MOOD_LABELS[quote.mood]}{MOOD_RULES[quote.mood]}"
    )


def build_workday_card(
    *,
    day: date,
    sign: str,
    content: DailyContent,
    picks: list[Candidate],
    chief: tuple[str, str] | None,
    cached_on: str | None,
    quote: StockQuote | None = None,
    sign_members: list[str] | None = None,
) -> dict:
    title = f"🍱 午餐吃什麼？ {day.month}/{day.day}（{WEEKDAY_NAMES[day.weekday()]}）"
    body = [text_block(title, size="Large", weight="Bolder")]
    if content.fortune:
        who = f"（{'、'.join(sign_members)}）" if sign_members else ""
        body.append(
            text_block(f"🔮 **今日幸運星座：{sign}**{who}\n\n{content.fortune}")
        )
    if quote:
        body.append(text_block(market_line(quote)))
    for index, candidate in enumerate(picks, start=1):
        body += _candidate_blocks(index, candidate)
    if not picks:
        body.append(text_block("今天找不到符合條件的店，請午餐長自由發揮 🙏"))
    if cached_on:
        body.append(
            text_block(
                f"⚠️ 午餐地圖暫時連不上，店家資料是 {cached_on} 的快取", isSubtle=True
            )
        )
    chief_body, entities = _chief_blocks(chief)
    return _lunch_card(body + chief_body + _extra_blocks(content), entities)


def build_holiday_card(*, day: date, content: DailyContent) -> dict:
    title = f"🎉 {day.month}/{day.day} 放假快樂！"
    return _lunch_card(
        [text_block(title, size="Large", weight="Bolder"), *_extra_blocks(content)]
    )
