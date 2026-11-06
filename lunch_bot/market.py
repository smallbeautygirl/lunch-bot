"""Stock-market mood, copied from lunch-map.betoolman.com so the bot and the
site agree: TAIEX up → 加菜 (pricier shops likelier), down → 省一點."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

MOOD_THRESHOLD_PCT = 0.3
FANCY_PRICE_BAND = 3
FANCY_CATEGORIES = {"牛排", "海鮮", "火鍋"}
CHEAP_CATEGORIES = {"便當", "自助餐", "麵", "水餃", "小吃", "速食", "早餐"}
PCT_DECIMALS = 2


class Mood(StrEnum):
    UP = "up"
    FLAT = "flat"
    DOWN = "down"


class PriceTier(StrEnum):
    FANCY = "fancy"
    CHEAP = "cheap"


MOOD_LABELS = {Mood.UP: "加菜", Mood.FLAT: "平盤", Mood.DOWN: "省一點"}
MOOD_FACTORS = {
    Mood.UP: {PriceTier.FANCY: 2.2, PriceTier.CHEAP: 0.55},
    Mood.FLAT: {PriceTier.FANCY: 1.0, PriceTier.CHEAP: 1.0},
    Mood.DOWN: {PriceTier.FANCY: 0.4, PriceTier.CHEAP: 2.2},
}


@dataclass(frozen=True)
class StockQuote:
    name: str
    price: float
    previous_close: float
    # "截至 09:14" while the market trades, "11/5 收盤" otherwise.
    as_of: str
    page_url: str | None = None

    @property
    def linked_name(self) -> str:
        return f"[{self.name}]({self.page_url})" if self.page_url else self.name

    @property
    def pct(self) -> float:
        return (self.price / self.previous_close - 1) * 100

    @property
    def mood(self) -> Mood:
        # Rounded as displayed, so a card saying +0.30% never reads 平盤.
        pct = round(self.pct, PCT_DECIMALS)
        if pct >= MOOD_THRESHOLD_PCT:
            return Mood.UP
        if pct <= -MOOD_THRESHOLD_PCT:
            return Mood.DOWN
        return Mood.FLAT


def price_tier(shop: dict) -> PriceTier | None:
    if shop.get("price") is not None:
        return PriceTier.FANCY if shop["price"] >= FANCY_PRICE_BAND else PriceTier.CHEAP
    categories = set(shop.get("category") or [])
    if categories & FANCY_CATEGORIES:
        return PriceTier.FANCY
    if categories & CHEAP_CATEGORIES:
        return PriceTier.CHEAP
    return None


def market_factor(shop: dict, quote: StockQuote | None) -> float:
    tier = price_tier(shop)
    if quote is None or tier is None:
        return 1.0
    return MOOD_FACTORS[quote.mood][tier]
