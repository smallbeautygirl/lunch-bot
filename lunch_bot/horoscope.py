from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from .claude import ask_claude
from .zodiac import ZODIAC_SIGNS

MIN_STARS = 1
MAX_STARS = 5


class SignFortune(BaseModel):
    sign: str
    overall: str
    wealth_stars: int
    lucky_color: str


class Horoscope(BaseModel):
    fortunes: list[SignFortune]


def _build_prompt(day: date, signs: list[str], market_lines: list[str]) -> str:
    lines = [
        f"今天是 {day.isoformat()}，請用台灣繁體中文、輕鬆幽默的語氣，"
        f"為這些星座各寫一則今日運勢（純屬娛樂）：{'、'.join(signs)}。",
        "每個星座：overall 是一兩句整體運勢（可以帶到上班族日常），"
        f"wealth_stars 是 {MIN_STARS} 到 {MAX_STARS} 的財運星等，"
        "lucky_color 是一個幸運色。sign 照抄上面的星座名稱。",
        "各星座的星等要有高有低，不要全部一樣。",
    ]
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
    *, day: date, signs: list[str], market_lines: list[str]
) -> list[SignFortune]:
    horoscope = ask_claude(_build_prompt(day, signs, market_lines), Horoscope)
    return tidy_fortunes(horoscope.fortunes, signs) if horoscope else []
