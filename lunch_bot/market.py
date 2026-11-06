"""Stock-market mood, copied from lunch-map.betoolman.com so the bot and the
site agree: TAIEX up → 加菜 (pricier shops likelier), down → 省一點."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

MOOD_THRESHOLD_PCT = 0.3
FANCY_PRICE_BAND = 3
FANCY_CATEGORIES = {"牛排", "海鮮", "火鍋"}
CHEAP_CATEGORIES = {"便當", "自助餐", "麵", "水餃", "小吃", "速食", "早餐"}


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
class MarketQuote:
    index_name: str
    close_date: str
    pct: float

    @property
    def mood(self) -> Mood:
        if self.pct >= MOOD_THRESHOLD_PCT:
            return Mood.UP
        if self.pct <= -MOOD_THRESHOLD_PCT:
            return Mood.DOWN
        return Mood.FLAT


def parse_quote(raw: dict | None) -> MarketQuote | None:
    if not raw or raw.get("pct") is None:
        return None
    return MarketQuote(
        index_name=raw.get("index", "加權指數"),
        close_date=raw.get("date", ""),
        pct=float(raw["pct"]),
    )


def price_tier(shop: dict) -> PriceTier | None:
    if shop.get("price") is not None:
        return PriceTier.FANCY if shop["price"] >= FANCY_PRICE_BAND else PriceTier.CHEAP
    categories = set(shop.get("category") or [])
    if categories & FANCY_CATEGORIES:
        return PriceTier.FANCY
    if categories & CHEAP_CATEGORIES:
        return PriceTier.CHEAP
    return None


def market_factor(shop: dict, quote: MarketQuote | None) -> float:
    tier = price_tier(shop)
    if quote is None or tier is None:
        return 1.0
    return MOOD_FACTORS[quote.mood][tier]
