"""Quotes from Yahoo Finance's chart API — the same source lunch-map's own
/api/market uses, but with a timestamp, so a card can say whether a number is
intraday or a close."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote as url_quote

import requests

from .config import HTTP_TIMEOUT_SECONDS
from .market import StockQuote

logger = logging.getLogger(__name__)

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
# Yahoo answers 429 to the default python-requests User-Agent.
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}
# Daily bars for a week: enough to find the last close before the quote's day
# across a long weekend.
YAHOO_PARAMS = {"interval": "1d", "range": "5d"}
YAHOO_QUOTE_PAGE_URL = "https://tw.stock.yahoo.com/quote/{symbol}"

TAIEX = ("^TWII", "加權指數")
OVERSEAS = (
    ("^GSPC", "S&P 500"),
    ("^IXIC", "那斯達克"),
    ("^SOX", "費城半導體"),
    ("TSM", "台積電 ADR"),
    # Linker Vision's main platform partner; the group follows it anyway.
    ("NVDA", "NVIDIA"),
)


def _closes_by_day(chart: dict, exchange_tz: timezone) -> dict[date, float]:
    timestamps = chart.get("timestamp") or []
    closes = chart.get("indicators", {}).get("quote", [{}])[0].get("close") or []
    return {
        datetime.fromtimestamp(stamp, exchange_tz).date(): close
        for stamp, close in zip(timestamps, closes, strict=False)
        if close is not None
    }


def parse_chart(chart: dict, name: str) -> StockQuote | None:
    """Previous close is the last daily close *before* the quote's own day.
    Yahoo's meta.chartPreviousClose can't be trusted for this: on 2026-11-06
    it still held 11/4's close beside 11/6's price, turning a -4.5% day into
    -7.56%."""
    meta = chart.get("meta", {})
    price = meta.get("regularMarketPrice")
    traded_at = meta.get("regularMarketTime")
    if not (price and traded_at):
        return None
    exchange_tz = timezone(timedelta(seconds=meta.get("gmtoffset", 0)))
    moment = datetime.fromtimestamp(traded_at, exchange_tz)
    earlier = {
        day: close
        for day, close in _closes_by_day(chart, exchange_tz).items()
        if day < moment.date()
    }
    if not earlier:
        return None
    regular = meta.get("currentTradingPeriod", {}).get("regular", {})
    is_trading = regular.get("start", 0) <= traded_at < regular.get("end", 0)
    as_of = (
        f"截至 {moment:%H:%M}" if is_trading else f"{moment.month}/{moment.day} 收盤"
    )
    return StockQuote(name, float(price), float(earlier[max(earlier)]), as_of)


def fetch_stock(symbol: str, name: str) -> StockQuote | None:
    try:
        response = requests.get(
            YAHOO_CHART_URL.format(symbol=symbol),
            params=YAHOO_PARAMS,
            headers=YAHOO_HEADERS,
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        chart = response.json()["chart"]["result"][0]
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        logger.warning("Quote unavailable", extra={"symbol": symbol})
        return None
    quote = parse_chart(chart, name)
    if quote is None:
        return None
    return replace(quote, page_url=quote_page_url(symbol))


def quote_page_url(symbol: str) -> str:
    return YAHOO_QUOTE_PAGE_URL.format(symbol=url_quote(symbol, safe=""))


def fetch_overseas() -> list[StockQuote]:
    quotes = (fetch_stock(symbol, name) for symbol, name in OVERSEAS)
    return [quote for quote in quotes if quote is not None]
