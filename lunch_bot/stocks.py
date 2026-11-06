"""Quotes from Yahoo Finance's chart API — the same source lunch-map's own
/api/market uses, but with a timestamp, so a card can say whether a number is
intraday or a close."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import requests

from .config import HTTP_TIMEOUT_SECONDS
from .market import StockQuote

logger = logging.getLogger(__name__)

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
# Yahoo answers 429 to the default python-requests User-Agent.
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}
YAHOO_PARAMS = {"interval": "5m", "range": "1d"}

TAIEX = ("^TWII", "加權指數")
OVERSEAS = (
    ("^GSPC", "S&P 500"),
    ("^IXIC", "那斯達克"),
    ("^SOX", "費城半導體"),
    ("TSM", "台積電 ADR"),
)


def parse_chart(meta: dict, name: str) -> StockQuote | None:
    price = meta.get("regularMarketPrice")
    previous_close = meta.get("chartPreviousClose")
    traded_at = meta.get("regularMarketTime")
    if not (price and previous_close and traded_at):
        return None
    regular = meta.get("currentTradingPeriod", {}).get("regular", {})
    is_trading = regular.get("start", 0) <= traded_at < regular.get("end", 0)
    exchange_tz = timezone(timedelta(seconds=meta.get("gmtoffset", 0)))
    moment = datetime.fromtimestamp(traded_at, exchange_tz)
    as_of = (
        f"截至 {moment:%H:%M}" if is_trading else f"{moment.month}/{moment.day} 收盤"
    )
    return StockQuote(name, float(price), float(previous_close), as_of)


def fetch_stock(symbol: str, name: str) -> StockQuote | None:
    try:
        response = requests.get(
            YAHOO_CHART_URL.format(symbol=symbol),
            params=YAHOO_PARAMS,
            headers=YAHOO_HEADERS,
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        meta = response.json()["chart"]["result"][0]["meta"]
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        logger.warning("Quote unavailable", extra={"symbol": symbol})
        return None
    return parse_chart(meta, name)


def fetch_overseas() -> list[StockQuote]:
    quotes = (fetch_stock(symbol, name) for symbol, name in OVERSEAS)
    return [quote for quote in quotes if quote is not None]
