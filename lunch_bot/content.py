from __future__ import annotations

import random
from datetime import date
from enum import StrEnum

from pydantic import BaseModel

from .calendar_tw import DayKind
from .claude import ask_claude

# Haiku's jokes read like translated English puns nobody in the group got.
# A stronger model plus Taiwanese classics as the style anchor; jokes run
# about twice a week, so the extra cost is a few NT$ a month.
JOKE_MODEL = "claude-sonnet-5-5"
JOKE_PROMPT = (
    "joke：一則台灣人一看就懂的一問一答冷笑話，question 是問題、answer 是答案。"
    "主題不限，好笑最重要。用台灣日常用語，笑點可以是國語或台語的諧音、"
    "一詞兩義，或是腦筋急轉彎式的答案。"
    "不要翻譯外國笑話，不要用中國大陸用語，不要需要專業知識的哏。"
    "風格參考（不要照抄，也不要沿用同樣的主題）："
    "Q 綠豆從樓上摔下來會變成什麼？A 紅豆，因為流血了。"
    "Q 為什麼飛機飛那麼高都不會撞到星星？A 因為星星會閃。"
    "Q 哪一種花最沒力？A 茉莉花（台語聽起來像「沒力」）。"
    "Q 哪種動物最沒方向感？A 麋鹿（迷路）。"
    "寫完先自我檢查：如果是諧音，兩個詞必須真的同音或幾乎同音；"
    "explanation 要具體寫出是哪兩個詞同音、或哪個詞有兩種意思。"
    "說不清楚笑點的就換一則。"
)
# Rotating topics keep English lessons and trivia from repeating.
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
    explanation: str = ""


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
        ExtraKind.JOKE: JOKE_PROMPT,
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
    if ExtraKind.JOKE in extras:
        content = ask_claude(prompt, DailyContent, model=JOKE_MODEL, effort="high")
    else:
        content = ask_claude(prompt, DailyContent)
    if content is None:
        return DailyContent()
    content.favored_categories = [
        c for c in content.favored_categories if c in categories
    ]
    return content
