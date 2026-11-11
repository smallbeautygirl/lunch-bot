"""唐綺陽's weekly horoscope (唐陽雞酒屋 podcast), the factual base for the
morning card's daily fortunes. Each Monday's episode notes carry all twelve
signs as 累的 / 穩的 / 讚的 plus a work-and-love line per sign.

Without it, the model only had a date and a sign to go on and fell back on
stereotypes (every 牡羊 day was impulsive and three coffees)."""

from __future__ import annotations

import html
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from email.utils import parsedate_to_datetime

import requests

from .config import HTTP_TIMEOUT_SECONDS, TAIPEI
from .zodiac import normalize_sign

logger = logging.getLogger(__name__)

FEED_URL = "https://feed.firstory.me/rss/user/ckga7ibs77fgl0875bxwgl0y0"
SOURCE_NAME = "唐綺陽星座週報（唐陽雞酒屋）"
HEADER_PATTERN = re.compile(r"【唐綺陽(\d+)/(\d+)-(\d+)/(\d+)星座運勢週報】")
TIER_PATTERN = re.compile(r"【(累|穩|讚)的】")
SIGN_LINE_PATTERN = re.compile(r"^\s*(\S{2})：(.+?)\s*$", re.MULTILINE)
# The weekly notes spell it 魔羯; the bot uses 摩羯.
SIGN_SPELLINGS = {"魔羯": "摩羯"}


@dataclass(frozen=True)
class SignReading:
    tier: str
    note: str


@dataclass(frozen=True)
class WeeklyReading:
    theme: str
    start: date
    end: date
    url: str
    signs: dict[str, SignReading]

    @property
    def week_label(self) -> str:
        return f"{self.start.month}/{self.start.day}–{self.end.month}/{self.end.day}"

    def covers(self, day: date) -> bool:
        return self.start <= day <= self.end


def _plain_text(description: str) -> str:
    text = re.sub(r"</p>|<br\s*/?>", "\n", description)
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def _week_range(text: str, published: date) -> tuple[date, date] | None:
    match = HEADER_PATTERN.search(text)
    if match is None:
        return None
    start_month, start_day, end_month, end_day = map(int, match.groups())
    start = date(published.year, start_month, start_day)
    end_year = published.year + (1 if end_month < start_month else 0)
    return start, date(end_year, end_month, end_day)


def _sign_readings(text: str) -> dict[str, SignReading]:
    """A sign's line sits in the segment after its tier's 【X的】 marker."""
    readings: dict[str, SignReading] = {}
    parts = TIER_PATTERN.split(text)
    for tier, segment in zip(parts[1::2], parts[2::2], strict=True):
        for short_name, note in SIGN_LINE_PATTERN.findall(segment):
            sign = normalize_sign(SIGN_SPELLINGS.get(short_name, short_name))
            if sign:
                readings[sign] = SignReading(tier=f"{tier}的", note=note)
    return readings


def parse_feed_item(item: ET.Element) -> WeeklyReading | None:
    text = _plain_text(item.findtext("description") or "")
    published = parsedate_to_datetime(item.findtext("pubDate") or "")
    week = _week_range(text, published.astimezone(TAIPEI).date())
    signs = _sign_readings(text)
    if week is None or not signs:
        return None
    theme = re.sub(r"^【本週提醒】", "", item.findtext("title") or "").strip()
    return WeeklyReading(
        theme=theme,
        start=week[0],
        end=week[1],
        url=item.findtext("link") or "",
        signs=signs,
    )


def find_reading(feed_xml: bytes, day: date) -> WeeklyReading | None:
    for item in ET.fromstring(feed_xml).iter("item"):
        try:
            reading = parse_feed_item(item)
        except (ValueError, TypeError):
            continue
        if reading and reading.covers(day):
            return reading
    return None


def fetch_weekly_reading(day: date) -> WeeklyReading | None:
    """None when the week's episode is not out yet (it lands around 11:00 on
    Mondays, after the morning card) or the feed is unreachable."""
    try:
        response = requests.get(FEED_URL, timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        reading = find_reading(response.content, day)
    except (requests.RequestException, ET.ParseError):
        logger.warning("Weekly horoscope feed unavailable", exc_info=True)
        return None
    if reading is None:
        logger.info("No weekly horoscope covers today", extra={"day": day})
    return reading
