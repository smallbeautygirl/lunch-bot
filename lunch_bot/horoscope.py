from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from .claude import ask_claude
from .sign_sources import MAX_STARS, MIN_STARS, SignSources
from .zodiac import ZODIAC_SIGNS

WEEKDAY_NAMES = "一二三四五六日"
OPENING_MAX_CHARS = 150
# Without these bans every 牡羊 day read "impulsive, third coffee".
FRESHNESS_RULES = (
    "不要用星座刻板印象當梗（例如牡羊衝動、處女龜毛、天蠍記仇、雙子善變），"
    "也不要寫咖啡。每個星座寫一個具體、不重複的上班族生活情境，"
    "並配合今天是星期幾（週一收心、週五快放假之類）。"
)
SOURCE_RULES = (
    "下面是兩位占星師本週對各星座的看法。今日運勢要綜合兩邊的方向，"
    "換成今天的具體情境，不要照抄原句。wealth_stars 必須落在每個星座標示的範圍內。"
    "標示「兩派衝突」的星座，conflict_note 用一句話點出兩邊說法哪裡不同，"
    "再給一個今天的折衷建議；其他星座 conflict_note 留空。"
)


class SignFortune(BaseModel):
    sign: str
    overall: str
    wealth_stars: int
    lucky_color: str
    conflict_note: str = ""


class Horoscope(BaseModel):
    fortunes: list[SignFortune]


def _source_line(sign: str, sources: SignSources) -> str:
    parts = [sign]
    if sources.tang:
        parts.append(f"唐綺陽【{sources.tang.tier}】{sources.tang.note}")
    if sources.mafalda:
        tier = f"【{sources.mafalda_tier}】" if sources.mafalda_tier else ""
        parts.append(f"瑪法達{tier}{sources.mafalda.opening[:OPENING_MAX_CHARS]}")
    low, high = sources.star_range
    parts.append(f"財運 {low}–{high} 顆")
    if sources.is_clash:
        parts.append("⚠️兩派衝突")
    return "｜".join(parts)


def _source_lines(sources: dict[str, SignSources]) -> list[str]:
    if not any(s.tang or s.mafalda for s in sources.values()):
        return []
    return [SOURCE_RULES, *(_source_line(sign, s) for sign, s in sources.items())]


def _build_prompt(
    day: date, sources: dict[str, SignSources], market_lines: list[str]
) -> str:
    lines = [
        f"今天是 {day.isoformat()}（星期{WEEKDAY_NAMES[day.weekday()]}），"
        "請用台灣繁體中文、輕鬆幽默的語氣，"
        f"為這些星座各寫一則今日運勢（純屬娛樂）：{'、'.join(sources)}。",
        "每個星座：overall 是一兩句整體運勢（可以帶到上班族日常），"
        f"wealth_stars 是 {MIN_STARS} 到 {MAX_STARS} 的財運星等，"
        "lucky_color 是一個幸運色。sign 照抄上面的星座名稱。",
        "各星座的星等要有高有低，不要全部一樣。",
        FRESHNESS_RULES,
        *_source_lines(sources),
    ]
    if market_lines:
        lines.append(
            "今天的股市可以拿來開玩笑，但不要給任何買賣建議：" + "；".join(market_lines)
        )
    return "\n".join(lines)


def _tidy_one(fortune: SignFortune, sources: SignSources | None) -> SignFortune:
    low, high = sources.star_range if sources else (MIN_STARS, MAX_STARS)
    stars = min(max(fortune.wealth_stars, low), high)
    note = fortune.conflict_note if sources and sources.is_clash else ""
    return fortune.model_copy(update={"wealth_stars": stars, "conflict_note": note})


def tidy_fortunes(
    fortunes: list[SignFortune],
    signs: list[str],
    sources: dict[str, SignSources] | None = None,
) -> list[SignFortune]:
    """One fortune per requested sign, in zodiac order, stars kept within the
    sources' range and clash notes only where the code found a clash — the
    model occasionally repeats, renames, over-scores or invents a conflict."""
    sources = sources or {}
    by_sign: dict[str, SignFortune] = {}
    for fortune in fortunes:
        if fortune.sign in signs and fortune.sign not in by_sign:
            by_sign[fortune.sign] = _tidy_one(fortune, sources.get(fortune.sign))
    return [by_sign[sign] for sign in ZODIAC_SIGNS if sign in by_sign]


def luckiest_signs(fortunes: list[SignFortune]) -> list[str]:
    if not fortunes:
        return []
    best = max(fortune.wealth_stars for fortune in fortunes)
    return [fortune.sign for fortune in fortunes if fortune.wealth_stars == best]


def generate_horoscope(
    *, day: date, sources: dict[str, SignSources], market_lines: list[str]
) -> list[SignFortune]:
    horoscope = ask_claude(_build_prompt(day, sources, market_lines), Horoscope)
    if horoscope is None:
        return []
    return tidy_fortunes(horoscope.fortunes, list(sources), sources)
