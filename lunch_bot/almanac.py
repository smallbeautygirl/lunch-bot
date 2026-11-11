"""職場版農民曆: the day's real 宜/忌 from the lunar calendar, each paired with a
workplace reading. The terms come from lunar-python, never from the model, so
the almanac part is genuine; Claude only writes the 「＝…」 jokes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from lunar_python import Solar
from opencc import OpenCC
from pydantic import BaseModel

from .claude import ask_claude

GOOD_SHOWN = 3
BAD_SHOWN = 2
WORKPLACE_TARGET_CHARS = 16
# Only a guard against a runaway reply: cutting at the target length left
# half-words like 「客戶立刻追加需」.
WORKPLACE_HARD_LIMIT = 40
# lunar-python answers in simplified Chinese.
TO_TAIWAN = OpenCC("s2tw")


@dataclass(frozen=True)
class Almanac:
    lunar_date: str
    clash_animal: str
    good: list[str]
    bad: list[str]


class TermReading(BaseModel):
    term: str
    workplace: str


class AlmanacReadings(BaseModel):
    readings: list[TermReading]


def compute_almanac(day: date) -> Almanac:
    lunar = Solar.fromYmd(day.year, day.month, day.day).getLunar()
    to_tw = TO_TAIWAN.convert
    return Almanac(
        lunar_date=to_tw(f"{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}"),
        clash_animal=to_tw(lunar.getDayChongShengXiao()),
        good=[to_tw(term) for term in lunar.getDayYi()[:GOOD_SHOWN]],
        bad=[to_tw(term) for term in lunar.getDayJi()[:BAD_SHOWN]],
    )


def _prompt(almanac: Almanac, workplace_context: str) -> str:
    terms = "、".join([*almanac.good, *almanac.bad])
    return "\n".join(
        [
            "幫農民曆的宜忌寫「職場版」翻譯，用台灣繁體中文，要好笑。",
            workplace_context,
            f"今天宜：{'、'.join(almanac.good)}；忌：{'、'.join(almanac.bad)}。",
            f"每個詞（{terms}）各寫一個 {WORKPLACE_TARGET_CHARS} 字以內的職場對應，"
            "要跟原本的意思有關聯，term 照抄原詞。"
            "宜的詞寫成今天適合做的工作事（例如出行→出差 demo、開光→新模型上線）；"
            "忌的詞寫成今天最好別做的工作事（例如動土→重構舊程式、掘井→改正式 DB），"
            "前面已經有「忌」字，所以不要再寫「別」「不要」。",
        ]
    )


def translate_almanac(almanac: Almanac, workplace_context: str) -> dict[str, str]:
    """Term → workplace reading; empty when Claude fails, and the card then
    shows the plain terms."""
    result = ask_claude(_prompt(almanac, workplace_context), AlmanacReadings)
    if result is None:
        return {}
    wanted = {*almanac.good, *almanac.bad}
    return {
        reading.term: reading.workplace.strip()
        for reading in result.readings
        if reading.term in wanted
        and 0 < len(reading.workplace.strip()) <= WORKPLACE_HARD_LIMIT
    }


def almanac_lines(almanac: Almanac, readings: dict[str, str]) -> list[str]:
    def describe(term: str) -> str:
        return f"{term}（{readings[term]}）" if term in readings else term

    return [
        f"📅 **職場農民曆**　農曆{almanac.lunar_date} · 沖{almanac.clash_animal}",
        f"✅ 宜：{'、'.join(describe(term) for term in almanac.good)}",
        f"⛔ 忌：{'、'.join(describe(term) for term in almanac.bad)}",
    ]
