"""Allergen warnings on the lunch picks. lunch-map knows a shop's category,
not its menu, so what a shop "probably uses" is Claude's guess from its name
and category, cached per shop: a hint to go and ask, never a guarantee.

Who is allergic to what is health data and lives in the MEMBER_ALLERGENS
secret; the guesses are about shops only and are safe to commit.

python -m lunch_bot.allergens   # guess for every shop not in the cache yet
"""

from __future__ import annotations

import json
import logging
import os
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from .claude import ask_claude
from .config import DATA_DIR, TAIPEI
from .lunch_map import load_lunch_map
from .picker import Candidate

logger = logging.getLogger(__name__)

SHOP_ALLERGENS_PATH = DATA_DIR / "shop_allergens.json"
# A fixed list, so the committed guesses say nothing about the group and a
# new member's allergens need no second pass over 477 shops.
ALLERGENS = ("蛋", "奶類", "小麥", "堅果", "花生", "大豆", "甲殼類", "魚", "芝麻")
BATCH_SIZE = 40
NOTE_MAX_CHARS = 40
DISCLAIMER = "⚠️ 過敏原是依店家類型推測的，實際請問店家"


@dataclass(frozen=True)
class MemberAllergens:
    name: str
    severe: frozenset[str]
    moderate: frozenset[str]

    @property
    def all(self) -> frozenset[str]:
        return self.severe | self.moderate


class ShopGuess(BaseModel):
    id: str
    is_unknown: bool
    allergens: list[str]


class ShopGuesses(BaseModel):
    shops: list[ShopGuess]


def _known(terms: object) -> frozenset[str]:
    return frozenset(str(term) for term in terms or [] if str(term) in ALLERGENS)


def read_member_allergens() -> list[MemberAllergens]:
    """MEMBER_ALLERGENS is {"name": {"severe": [...], "moderate": [...]}},
    in the words of ALLERGENS."""
    raw = os.getenv("MEMBER_ALLERGENS", "").strip()
    if not raw:
        return []
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("MEMBER_ALLERGENS is not valid JSON")
        return []
    if not isinstance(entries, dict):
        logger.warning("MEMBER_ALLERGENS must be a JSON object")
        return []
    members = [
        MemberAllergens(
            str(name), _known(entry.get("severe")), _known(entry.get("moderate"))
        )
        for name, entry in entries.items()
        if isinstance(entry, dict)
    ]
    if os.getenv("GITHUB_ACTIONS") == "true":
        # A dry run prints the card into a public log: never name whose.
        for member in members:
            print(f"::add-mask::{member.name}")
    return [member for member in members if member.all]


def load_shop_allergens(
    path: Path = SHOP_ALLERGENS_PATH,
) -> dict[str, list[str] | None]:
    """Shop id → guessed allergens; None when the shop's type says nothing."""
    return json.loads(path.read_text()) if path.exists() else {}


def is_safe_for_all(
    shop_id: str, guesses: dict[str, list[str] | None], members: list[MemberAllergens]
) -> bool:
    """Guessed free of everyone's severe allergens. A shop without a usable
    guess is never called safe."""
    guess = guesses.get(shop_id)
    if guess is None:
        return False
    severe = frozenset().union(*(member.severe for member in members))
    return not severe & set(guess)


def warnings_for(
    shop_id: str, guesses: dict[str, list[str] | None], members: list[MemberAllergens]
) -> list[str]:
    guess = guesses.get(shop_id)
    if guess is None:
        return []
    lines = []
    for member in members:
        hits = [
            allergen for allergen in ALLERGENS if allergen in member.all & set(guess)
        ]
        if hits:
            lines.append(f"⚠️ {member.name} 注意：可能含{'、'.join(hits)}")
    return lines


def ensure_safe_pick(
    picks: list[Candidate],
    candidates: list[Candidate],
    guesses: dict[str, list[str] | None],
    members: list[MemberAllergens],
    rng: random.Random,
) -> list[Candidate]:
    """At least one pick guessed safe for everyone: when none is, the last
    pick (the random one) gives way to a safe candidate, if there is any."""
    if not members or not picks:
        return picks
    if any(is_safe_for_all(pick.shop["id"], guesses, members) for pick in picks):
        return picks
    picked = {pick.shop["id"] for pick in picks}
    safe = [
        candidate
        for candidate in candidates
        if candidate.shop["id"] not in picked
        and is_safe_for_all(candidate.shop["id"], guesses, members)
    ]
    return [*picks[:-1], rng.choice(safe)] if safe else picks


def _shop_line(shop: dict) -> str:
    note = (shop.get("note") or "")[:NOTE_MAX_CHARS]
    return f"{shop['id']}｜{shop['name']}｜{'、'.join(shop['category'])}｜{note}"


def _prompt(shops: list[dict]) -> str:
    return "\n".join(
        [
            "下面是台灣高雄的餐廳，每行是「id｜店名｜分類｜備註」。"
            "請依店名和分類，推測每家店的主力餐點多半會用到哪些過敏原，"
            f"只能從這些裡面選：{'、'.join(ALLERGENS)}。",
            "只算主要食材（麵條和餃子皮算小麥、早午餐算蛋和奶類、起司和奶茶算奶類），"
            "不算醬油之類的調味料，也不算可能的微量混入。",
            "從店名和分類看不出賣什麼的（例如分類是「其他」而店名沒有線索），"
            "is_unknown 設為 true、allergens 留空；看得出來而且確實都用不到的，"
            "is_unknown 設為 false、allergens 留空。id 照抄。",
            *(_shop_line(shop) for shop in shops),
        ]
    )


def guess_shop_allergens(shops: list[dict]) -> dict[str, list[str] | None]:
    """Guesses for the shops Claude answered about; a failed batch is simply
    missing and gets asked again on the next run."""
    guesses: dict[str, list[str] | None] = {}
    for start in range(0, len(shops), BATCH_SIZE):
        batch = shops[start : start + BATCH_SIZE]
        wanted = {shop["id"] for shop in batch}
        result = ask_claude(_prompt(batch), ShopGuesses)
        for guess in result.shops if result else []:
            if guess.id in wanted:
                known = [a for a in ALLERGENS if a in guess.allergens]
                guesses[guess.id] = None if guess.is_unknown else known
    return guesses


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    cached = load_shop_allergens()
    shops = load_lunch_map(datetime.now(TAIPEI).date()).shops
    missing = [shop for shop in shops if shop["id"] not in cached]
    guesses = {**cached, **guess_shop_allergens(missing)}
    logger.info(
        "Shops guessed: %d of %d missing", len(guesses) - len(cached), len(missing)
    )
    SHOP_ALLERGENS_PATH.write_text(
        json.dumps(guesses, ensure_ascii=False, indent=1, sort_keys=True)
    )


if __name__ == "__main__":
    main()
