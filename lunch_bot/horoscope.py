from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from .claude import ask_claude
from .weekly_reading import WeeklyReading
from .zodiac import ZODIAC_SIGNS

MIN_STARS = 1
MAX_STARS = 5
WEEKDAY_NAMES = "一二三四五六日"
# Without these bans every 牡羊 day read "impulsive, third coffee".
FRESHNESS_RULES = (
    "不要用星座刻板印象當梗（例如牡羊衝動、處女龜毛、天蠍記仇、雙子善變），"
    "也不要寫咖啡。每個星座寫一個具體、不重複的上班族生活情境，"
    "並配合今天是星期幾（週一收心、週五快放假之類）。"
)


class SignFortune(BaseModel):
    sign: str
    overall: str
    wealth_stars: int
    lucky_color: str


class Horoscope(BaseModel):
    fortunes: list[SignFortune]


def _weekly_lines(reading: WeeklyReading, signs: list[str]) -> list[str]:
    notes = [
        f"{sign}【{reading.signs[sign].tier}】{reading.signs[sign].note}"
        for sign in signs
        if sign in reading.signs
    ]
    return [
        f"參考唐綺陽本週（{reading.week_label}）星座週報，"
        f"本週主題：「{reading.theme}」。各星座本週方向：" + "；".join(notes) + "。",
        "今日運勢要順著該星座本週的方向寫，但換成今天的具體情境，不要照抄原句。"
        "財運星等也要對應：讚的 4–5 顆，穩的 3 顆左右，累的 1–2 顆。",
    ]


def _build_prompt(
    day: date,
    signs: list[str],
    market_lines: list[str],
    reading: WeeklyReading | None,
) -> str:
    lines = [
        f"今天是 {day.isoformat()}（星期{WEEKDAY_NAMES[day.weekday()]}），"
        "請用台灣繁體中文、輕鬆幽默的語氣，"
        f"為這些星座各寫一則今日運勢（純屬娛樂）：{'、'.join(signs)}。",
        "每個星座：overall 是一兩句整體運勢（可以帶到上班族日常），"
        f"wealth_stars 是 {MIN_STARS} 到 {MAX_STARS} 的財運星等，"
        "lucky_color 是一個幸運色。sign 照抄上面的星座名稱。",
        "各星座的星等要有高有低，不要全部一樣。",
        FRESHNESS_RULES,
    ]
    if reading:
        lines += _weekly_lines(reading, signs)
    if market_lines:
        lines.append(
            "今天的股市可以拿來開玩笑，但不要給任何買賣建議：" + "；".join(market_lines)
        )
    return "\n".join(lines)


def tidy_fortunes(fortunes: list[SignFortune], signs: list[str]) -> list[SignFortune]:
    """One fortune per requested sign, in zodiac order, stars kept in range —
    the model occasionally repeats, renames, or over-scores a sign."""
    by_sign: dict[str, SignFortune] = {}
    for fortune in fortunes:
        if fortune.sign in signs and fortune.sign not in by_sign:
            stars = min(max(fortune.wealth_stars, MIN_STARS), MAX_STARS)
            by_sign[fortune.sign] = fortune.model_copy(update={"wealth_stars": stars})
    return [by_sign[sign] for sign in ZODIAC_SIGNS if sign in by_sign]


def luckiest_signs(fortunes: list[SignFortune]) -> list[str]:
    if not fortunes:
        return []
    best = max(fortune.wealth_stars for fortune in fortunes)
    return [fortune.sign for fortune in fortunes if fortune.wealth_stars == best]


def generate_horoscope(
    *,
    day: date,
    signs: list[str],
    market_lines: list[str],
    reading: WeeklyReading | None,
) -> list[SignFortune]:
    prompt = _build_prompt(day, signs, market_lines, reading)
    horoscope = ask_claude(prompt, Horoscope)
    return tidy_fortunes(horoscope.fortunes, signs) if horoscope else []
