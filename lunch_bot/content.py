from __future__ import annotations

import logging
import os
import random
from datetime import date
from enum import StrEnum

import anthropic
from pydantic import BaseModel

from .calendar_tw import DayKind
from .config import CLAUDE_MODEL

logger = logging.getLogger(__name__)

ZODIAC_SIGNS = (
    "牡羊座",
    "金牛座",
    "雙子座",
    "巨蟹座",
    "獅子座",
    "處女座",
    "天秤座",
    "天蠍座",
    "射手座",
    "摩羯座",
    "水瓶座",
    "雙魚座",
)
# Rotating topics keep Haiku from telling the same joke every day.
TOPICS = (
    "動物",
    "辦公室",
    "食物",
    "天氣",
    "交通",
    "科技",
    "運動",
    "歷史",
    "太空",
    "語言",
)
MAX_OUTPUT_TOKENS = 4000


class ExtraKind(StrEnum):
    JOKE = "joke"
    ENGLISH = "english"
    TRIVIA = "trivia"


WEEKDAY_EXTRAS = (
    ExtraKind.JOKE,
    ExtraKind.ENGLISH,
    ExtraKind.TRIVIA,
    ExtraKind.ENGLISH,
    ExtraKind.JOKE,
    ExtraKind.TRIVIA,
    ExtraKind.TRIVIA,
)


class EnglishLesson(BaseModel):
    sentence: str
    translation: str
    keyword: str
    keyword_meaning: str


class DailyContent(BaseModel):
    fortune: str | None = None
    favored_categories: list[str] = []
    joke: str | None = None
    english: EnglishLesson | None = None
    trivia: str | None = None


def extras_for(day: date, kind: DayKind) -> list[ExtraKind]:
    if kind is DayKind.NATIONAL_HOLIDAY:
        return [ExtraKind.ENGLISH, ExtraKind.JOKE]
    return [WEEKDAY_EXTRAS[day.weekday()]]


def _build_prompt(
    *,
    day: date,
    sign: str | None,
    categories: list[str],
    extras: list[ExtraKind],
    topic: str,
) -> str:
    lines = [f"今天是 {day.isoformat()}，請用台灣繁體中文，語氣輕鬆。"]
    if sign:
        lines.append(
            f"為「{sign}」寫一兩句今日運勢（純屬娛樂），並給午餐建議；"
            f"從這些店家分類挑 1 到 3 個最符合運勢的填入 favored_categories："
            f"{'、'.join(categories)}。"
            "運勢裡的午餐建議只能提到你填入 favored_categories 的分類名稱，"
            "不要提其他食物，也不要寫「其他」這個分類。"
        )
    wanted = {
        ExtraKind.JOKE: f"joke：一則和「{topic}」有關、適合辦公室的短笑話。",
        ExtraKind.ENGLISH: f"english：一句和「{topic}」有關的實用英文、中文翻譯、"
        "一個重點單字和它的意思。",
        ExtraKind.TRIVIA: f"trivia：一則和「{topic}」有關、可查證的冷知識，一兩句。",
    }
    lines += [wanted[extra] for extra in extras]
    lines.append("沒被要求的欄位留空。")
    return "\n".join(lines)


def generate_content(
    *,
    day: date,
    sign: str | None,
    categories: list[str],
    extras: list[ExtraKind],
    rng: random.Random,
) -> DailyContent:
    """Never blocks the lunch post: on any API failure it returns empty
    content and the message goes out without the fun parts."""
    topic = rng.choice(TOPICS)
    if not os.getenv("ANTHROPIC_API_KEY"):
        # The SDK raises TypeError (not APIError) when it has no credentials.
        logger.warning("ANTHROPIC_API_KEY not set, skipping generated content")
        return DailyContent()
    prompt = _build_prompt(
        day=day,
        sign=sign,
        categories=categories,
        extras=extras,
        topic=topic,
    )
    try:
        response = anthropic.Anthropic().messages.parse(
            model=CLAUDE_MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
            output_format=DailyContent,
        )
    except anthropic.APIError as error:
        logger.warning("Claude content failed", extra={"error": str(error)})
        return DailyContent()
    if response.stop_reason != "end_turn" or response.parsed_output is None:
        logger.warning("Claude content unusable", extra={"stop": response.stop_reason})
        return DailyContent()
    content = response.parsed_output
    content.favored_categories = [
        c for c in content.favored_categories if c in categories
    ]
    return content
