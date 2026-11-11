"""瑪法達's weekly horoscope (鏡週刊, on LINE TODAY), the second source beside
唐綺陽's. Weeks run Wednesday to Tuesday, out around 07:58 on Wednesdays.

The ★ ratings on her pages are the week's overall mood, identical on all
twelve signs, so a sign's standing comes from the 星座排行 (top four) and the
signs she names as slipping; the per-sign text is each page's opening
paragraph. LINE TODAY has no feed, so this parses HTML and its wording varies
week to week: whatever cannot be read is left out, never guessed."""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

import requests

from .config import HTTP_TIMEOUT_SECONDS
from .zodiac import ZODIAC_SIGNS, normalize_sign

logger = logging.getLogger(__name__)

PUBLISHER_URL = "https://today.line.me/tw/v3/publisher/101416"
ARTICLE_BASE_URL = "https://today.line.me"
SOURCE_NAME = "瑪法達星座運勢（鏡週刊）"
# LINE TODAY serves an empty shell to the default python-requests agent.
HEADERS = {"User-Agent": "Mozilla/5.0"}
LISTING_PATTERN = re.compile(
    r'href="(/tw/v3/article/\w+)"(?:(?!href=).)*?'
    r"<h3[^>]*>瑪法達星座運勢／(\S+?)\s*(\d+)\.(\d+)~(\d+)\.(\d+)</h3>",
    re.S,
)
ARTICLE_PATTERN = re.compile(r"<article[^>]*>(.*?)</article>", re.S)
PARAGRAPH_PATTERN = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
RANKING_PATTERN = re.compile(r"星座排行.*?<ul[^>]*>(.*?)</ul>", re.S)
RANKED_SIGN_PATTERN = re.compile(r"<li>\s*(\S{2}座)：")
# "本週運勢滑落的星座是：雙子、處女與天蠍座" / "本週運勢略嫌混亂的星座是：…"
SLIPPING_PATTERN = re.compile(r"本週運勢[^。：<]*的星座是：([^。<]+)")
SIGN_SEPARATORS = re.compile(r"[、與和及]")
SIGN_SPELLINGS = {"魔羯": "摩羯"}


class MafaldaTier(StrEnum):
    TOP = "前段班"
    NORMAL = "普通"
    SLIPPING = "滑落"


@dataclass(frozen=True)
class MafaldaSign:
    opening: str
    url: str
    tier: MafaldaTier | None


@dataclass(frozen=True)
class MafaldaReading:
    week_label: str
    signs: dict[str, MafaldaSign]


@dataclass(frozen=True)
class _ListedArticle:
    url: str
    week_label: str


def _to_sign(raw: str) -> str | None:
    name = raw.strip().removesuffix("座")
    return normalize_sign(SIGN_SPELLINGS.get(name, name))


def _week_dates(day: date, numbers: tuple[int, ...]) -> tuple[date, date]:
    start_month, start_day, end_month, end_day = numbers
    start_year = day.year - (1 if start_month > day.month else 0)
    end_year = start_year + (1 if end_month < start_month else 0)
    return (
        date(start_year, start_month, start_day),
        date(end_year, end_month, end_day),
    )


def find_articles(listing_html: str, day: date) -> dict[str, _ListedArticle]:
    """Sign → this week's article, for the week that covers the day."""
    articles: dict[str, _ListedArticle] = {}
    for match in LISTING_PATTERN.finditer(listing_html):
        path, raw_sign, *raw_numbers = match.groups()
        numbers = tuple(int(number) for number in raw_numbers)
        start, end = _week_dates(day, numbers)
        sign = _to_sign(raw_sign)
        if sign and start <= day <= end and sign not in articles:
            label = f"{start.month}/{start.day}–{end.month}/{end.day}"
            articles[sign] = _ListedArticle(f"{ARTICLE_BASE_URL}{path}", label)
    return articles


def _plain(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def parse_opening(article_html: str) -> str | None:
    article = ARTICLE_PATTERN.search(article_html)
    if article is None:
        return None
    paragraph = PARAGRAPH_PATTERN.search(article.group(1))
    return _plain(paragraph.group(1)) if paragraph else None


def parse_standings(article_html: str) -> dict[str, MafaldaTier] | None:
    """Every sign's tier, or None when this week's ranking can't be read."""
    ranking = RANKING_PATTERN.search(article_html)
    if ranking is None:
        return None
    top = {_to_sign(raw) for raw in RANKED_SIGN_PATTERN.findall(ranking.group(1))}
    slipping_match = SLIPPING_PATTERN.search(article_html)
    slipping = (
        {_to_sign(raw) for raw in SIGN_SEPARATORS.split(slipping_match.group(1))}
        if slipping_match
        else set()
    )
    tiers: dict[str, MafaldaTier] = {}
    for sign in ZODIAC_SIGNS:
        if sign in top and sign in slipping:
            # Her pages have listed a sign as both; no tier beats a wrong one.
            continue
        if sign in top:
            tiers[sign] = MafaldaTier.TOP
        elif sign in slipping:
            tiers[sign] = MafaldaTier.SLIPPING
        else:
            tiers[sign] = MafaldaTier.NORMAL
    return tiers


def _get(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def _read_sign(
    article: _ListedArticle, standings: dict[str, MafaldaTier] | None, sign: str
) -> tuple[MafaldaSign | None, dict[str, MafaldaTier] | None]:
    page = _get(article.url)
    standings = standings or parse_standings(page)
    opening = parse_opening(page)
    if opening is None:
        return None, standings
    tier = standings.get(sign) if standings else None
    return MafaldaSign(opening=opening, url=article.url, tier=tier), standings


def fetch_mafalda_reading(day: date, signs: list[str]) -> MafaldaReading | None:
    """None when this week's pages are not up yet or LINE TODAY is unreachable;
    only the requested signs' pages are fetched."""
    try:
        articles = find_articles(_get(PUBLISHER_URL), day)
        standings: dict[str, MafaldaTier] | None = None
        readings: dict[str, MafaldaSign] = {}
        for sign in signs:
            if sign not in articles:
                continue
            reading, standings = _read_sign(articles[sign], standings, sign)
            if reading:
                readings[sign] = reading
    except requests.RequestException:
        logger.warning("瑪法達 pages unavailable", exc_info=True)
        return None
    if not readings:
        logger.info("No 瑪法達 reading covers today", extra={"day": day})
        return None
    week_label = next(iter(articles.values())).week_label
    return MafaldaReading(week_label=week_label, signs=readings)
