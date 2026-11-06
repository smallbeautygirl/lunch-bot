from __future__ import annotations

import random
from datetime import date
from enum import StrEnum

from pydantic import BaseModel

from .calendar_tw import DayKind
from .claude import ask_claude

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


class Joke(BaseModel):
    question: str
    answer: str


class EnglishLesson(BaseModel):
    sentence: str
    translation: str
    keyword: str
    keyword_meaning: str


class DailyContent(BaseModel):
    fortune: str | None = None
    favored_categories: list[str] = []
    joke: Joke | None = None
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
        ExtraKind.JOKE: f"joke：一則和「{topic}」有關的一問一答冷笑話或諧音梗，"
        "question 是問題、answer 是答案；不需要背景知識，台灣上班族一看就懂。",
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
    prompt = _build_prompt(
        day=day,
        sign=sign,
        categories=categories,
        extras=extras,
        topic=topic,
    )
    content = ask_claude(prompt, DailyContent)
    if content is None:
        return DailyContent()
    content.favored_categories = [
        c for c in content.favored_categories if c in categories
    ]
    return content
