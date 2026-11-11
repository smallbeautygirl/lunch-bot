from __future__ import annotations

import random
from datetime import date
from enum import StrEnum

from pydantic import BaseModel

from .calendar_tw import DayKind
from .claude import ask_claude
from .horoscope import (
    FRAMING_RULES,
    FRESHNESS_RULES,
    WORKPLACE_CONTEXT,
    source_line,
)
from .market import Mood
from .roles import ROLE_SCENES
from .sign_sources import SignSources

# Haiku's jokes read like translated English puns nobody in the group got,
# and Chinese homophones are exactly what it gets wrong. Jokes and English
# (the 諧音 mnemonic) use a stronger model; together they run four days a
# week, still a few NT$ a month.
WORDPLAY_MODEL = "claude-sonnet-5-5"
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
    "說不清楚笑點的就換一則。"
    "explanation 是「笑點解析」，同事覺得這段最好笑：用一本正經、"
    "像學術論文或新聞稿的口吻，把冷笑話分析得太認真、解釋過頭，"
    "但內容要正確，具體點出是哪兩個詞同音、或哪個詞有兩種意思。"
    "兩三句以內。口吻示範（只學口吻，不要用這個題材）：「本笑話運用『凍結』一詞之雙關，"
    "於語意層面同時指涉物理低溫與金融管制，形成認知落差，"
    "研究團隊建議讀者自行斟酌是否發笑。」"
    "示範的句子不要照抄，每次換一種正經口吻：論文摘要、新聞快訊、"
    "產品說明書、法律條文、氣象報告、主管簡報都可以。"
)
ENGLISH_PROMPT = (
    "english：用「諧音記憶法」教一個英文單字，最好和「{topic}」有關。"
    "程度要中高級（多益 800 分、大學程度以上），不要 apple、happy、meeting "
    "這種上班族早就會的字。word 是單字，meaning 是中文意思。"
    "mnemonic：找一段念起來像這個英文單字發音的中文（國語或台語都可以），"
    "再用一兩句編一個好笑、有畫面的情境，把諧音和字義連在一起，"
    "讓人記得很怪但忘不掉。諧音那段用「」框起來。"
    "風格參考（不要照抄這些字）："
    "kangaroo 袋鼠 → 袋鼠跳太快，每跳一下都要停下來「看個路」。"
    "ambulance 救護車 → 躺在救護車上的人一直喊「俺不能死」。"
    "ambition 雄心 → 有雄心的人每天對鏡子喊「俺必勝」。"
    "寫完先自我檢查：把英文單字念出來，諧音必須真的聽起來像；"
    "對不上的就換一個單字。"
    "sentence 是一句用到這個單字的實用英文例句，translation 是它的中文翻譯。"
)
# The picks follow the market (加菜 only $$+, 省一點 only $); a fortune saying
# "play it safe with a 便當" above three $$$ shops reads as a contradiction.
MOOD_LUNCH_HINTS = {
    Mood.UP: "今天台股大漲是加菜日，推薦的店都是 $$ 以上，"
    "午餐建議要往吃好一點的方向寫。",
    Mood.DOWN: "今天台股下跌是省一點日，推薦的店都是平價的 $，"
    "午餐建議要往省錢的方向寫。",
}
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
    word: str
    meaning: str
    # 諧音記憶: a Chinese phrase that sounds like the word, plus a silly scene
    # tying it to the meaning (kangaroo → 袋鼠「看個路」).
    mnemonic: str
    sentence: str
    translation: str


WORDPLAY_EXTRAS = {ExtraKind.JOKE, ExtraKind.ENGLISH}


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


def _fortune_lines(
    sign: str,
    categories: list[str],
    sources: SignSources | None,
    mix: str,
    mood: Mood | None,
) -> list[str]:
    """Same voice as the morning card's horoscope, so the lucky sign at lunch
    reads like the 09:10 one rather than a generic fortune cookie."""
    lines = [
        f"為「{sign}」寫今日運勢（純屬娛樂），fortune 最多兩句、不超過 60 字："
        "第一句是帶公司日常的建議，第二句是午餐建議，要有幽默或反差。"
        f"從這些店家分類挑 1 到 3 個最符合運勢的填入 favored_categories："
        f"{'、'.join(categories)}。"
        "午餐建議只能提到你填入 favored_categories 的分類名稱，"
        "不要提其他食物，也不要寫「其他」這個分類。",
        FRESHNESS_RULES,
        WORKPLACE_CONTEXT,
        FRAMING_RULES,
    ]
    if mix:
        lines += [ROLE_SCENES, f"{sign}的成員角色：{mix}。"]
    if mood in MOOD_LUNCH_HINTS:
        lines.append(MOOD_LUNCH_HINTS[mood])
    if sources and (sources.tang or sources.mafalda):
        lines.append(
            "參考兩位占星師本週對這個星座的看法，綜合兩邊的方向，不要照抄原句"
            "（標示「兩派衝突」時取折衷）："
            + source_line(sign, sources, with_stars=False)
        )
    return lines


def _build_prompt(
    *,
    day: date,
    sign: str | None,
    categories: list[str],
    extras: list[ExtraKind],
    topic: str,
    sources: SignSources | None = None,
    mix: str = "",
    mood: Mood | None = None,
) -> str:
    lines = [f"今天是 {day.isoformat()}，請用台灣繁體中文，語氣輕鬆。"]
    if sign:
        lines += _fortune_lines(sign, categories, sources, mix, mood)
    wanted = {
        ExtraKind.JOKE: JOKE_PROMPT,
        ExtraKind.ENGLISH: ENGLISH_PROMPT.format(topic=topic),
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
    sources: SignSources | None = None,
    mix: str = "",
    mood: Mood | None = None,
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
        sources=sources,
        mix=mix,
        mood=mood,
    )
    if WORDPLAY_EXTRAS & set(extras):
        content = ask_claude(prompt, DailyContent, model=WORDPLAY_MODEL, effort="high")
    else:
        content = ask_claude(prompt, DailyContent)
    if content is None:
        return DailyContent()
    content.favored_categories = [
        c for c in content.favored_categories if c in categories
    ]
    return content
