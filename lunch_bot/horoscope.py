from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from .claude import ask_claude
from .roles import ROLE_SCENES
from .sign_sources import MAX_STARS, MIN_STARS, SignSources
from .zodiac import ZODIAC_SIGNS

WEEKDAY_NAMES = "一二三四五六日"
OPENING_MAX_CHARS = 150
# Without these bans every 牡羊 day read "impulsive, third coffee".
FRESHNESS_RULES = (
    "不要用星座刻板印象當梗（例如牡羊衝動、處女龜毛、天蠍記仇、雙子善變），"
    "也不要寫咖啡。每個星座的角度都要不一樣，"
    "整張卡最多只有一個星座提到今天星期幾（週一收心、週五快放假之類），其他不要提。"
)
# Only what linkervision.com says publicly: this repo and its Actions logs are
# public, so no customer, project or internal service names belong here.
WORKPLACE_CONTEXT = (
    "讀者是 Linker Vision 的同事，做視覺 AI 平台（Linker AI Nexa）："
    "Mirra 合成資料、DataVerse 模型訓練、Observ 大規模 VLM 部署，"
    "應用在智慧城市、捷運機場港口等關鍵基礎設施、工廠和數位分身，"
    "和 NVIDIA 合作很深。群組裡有 BD、PM、FAE、RD、DevOps 和 RD 主管，"
    "內容要貼近他們各自的職位，不要每個人都寫成在跑 GPU。"
    "公司用 Teams 溝通（不是 Slack）。"
    "偶爾提到產品名就好，不要每則都提，也不要編造客戶或案子名稱。"
)
# A concrete prediction that doesn't happen reads as "not accurate"; advice
# and if-then framing keep the workplace flavour without being falsifiable.
FRAMING_RULES = (
    "用建議或「如果……就……」的口吻寫（今天適合……、如果遇到……就……），"
    "不要斷言今天一定會發生的具體事件（例如「主管會稱讚你」）。"
)
SOURCE_RULES = (
    "下面是兩位占星師本週對各星座的看法。今日運勢要綜合兩邊的方向，"
    "寫成今天的建議，不要照抄原句。wealth_stars 必須落在每個星座標示的範圍內。"
    "標示「兩派衝突」的星座，conflict_note 用 30 字以內的一句話點出兩邊說法哪裡不同，"
    "再給一個今天的折衷建議；其他星座 conflict_note 留空。"
)


class SignFortune(BaseModel):
    sign: str
    overall: str
    wealth_stars: int
    lucky_color: str
    wealth_note: str = ""
    conflict_note: str = ""


class Horoscope(BaseModel):
    fortunes: list[SignFortune]


def source_line(sign: str, sources: SignSources, *, with_stars: bool = True) -> str:
    parts = [sign]
    if sources.tang:
        parts.append(f"唐綺陽【{sources.tang.tier}】{sources.tang.note}")
    if sources.mafalda:
        tier = f"【{sources.mafalda_tier}】" if sources.mafalda_tier else ""
        parts.append(f"瑪法達{tier}{sources.mafalda.opening[:OPENING_MAX_CHARS]}")
    if with_stars:
        low, high = sources.star_range
        parts.append(f"財運 {low}–{high} 顆")
    if sources.is_clash:
        parts.append("⚠️兩派衝突")
    return "｜".join(parts)


def _source_lines(sources: dict[str, SignSources]) -> list[str]:
    if not any(s.tang or s.mafalda for s in sources.values()):
        return []
    return [SOURCE_RULES, *(source_line(sign, s) for sign, s in sources.items())]


def _role_lines(mixes: dict[str, str]) -> list[str]:
    if not mixes:
        return []
    return [
        ROLE_SCENES,
        "各星座成員的角色：" + "；".join(f"{s}：{m}" for s, m in mixes.items()),
    ]


def _build_prompt(
    day: date,
    sources: dict[str, SignSources],
    market_lines: list[str],
    mixes: dict[str, str],
) -> str:
    lines = [
        f"今天是 {day.isoformat()}（星期{WEEKDAY_NAMES[day.weekday()]}），"
        "請用台灣繁體中文、輕鬆幽默的語氣，"
        f"為這些星座各寫一則今日運勢（純屬娛樂）：{'、'.join(sources)}。",
        "每個星座：overall 剛好兩句、不超過 70 字："
        "第一句是一般的星座運勢（心情、人際、感情、健康或整體運，參考占星師的看法），"
        "第二句才帶到工作，配合職位，要有幽默或反差（自嘲、誇張、吐槽都可以）。"
        f"wealth_stars 是 {MIN_STARS} 到 {MAX_STARS} 的財運星等，"
        "wealth_note 是 15 字以內的財運短評，語氣要跟星等一致（5 顆才能說大爆發），"
        "前面已經有「財運」兩字，不要再以「財運」開頭；可以拿今天股市開玩笑，"
        "但不能叫人買、賣或推薦任何標的。"
        "lucky_color 是一個幸運色。sign 照抄上面的星座名稱。",
        "各星座的星等要有高有低，不要全部一樣。",
        FRESHNESS_RULES,
        WORKPLACE_CONTEXT,
        FRAMING_RULES,
        *_role_lines(mixes),
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
    *,
    day: date,
    sources: dict[str, SignSources],
    market_lines: list[str],
    mixes: dict[str, str] | None = None,
) -> list[SignFortune]:
    prompt = _build_prompt(day, sources, market_lines, mixes or {})
    horoscope = ask_claude(prompt, Horoscope)
    if horoscope is None:
        return []
    return tidy_fortunes(horoscope.fortunes, list(sources), sources)
