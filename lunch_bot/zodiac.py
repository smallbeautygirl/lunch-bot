"""The twelve signs and which group member belongs to which. The member list
lives in the GROUP_MEMBERS secret, never in this public repo."""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

ZODIAC_SIGNS = (
    "牡羊座",
    "金牛座",
    "雙子座",
    "巨蟹座",
    "獅子座",
    "處女座",
    "天秤座",
    "天蠍座",
    "射手座",
    "摩羯座",
    "水瓶座",
    "雙魚座",
)
SIGN_SYMBOLS = dict(zip(ZODIAC_SIGNS, "♈♉♊♋♌♍♎♏♐♑♒♓", strict=True))
SIGN_SUFFIX = "座"


def normalize_sign(raw: str) -> str | None:
    sign = raw.strip()
    if not sign.endswith(SIGN_SUFFIX):
        sign += SIGN_SUFFIX
    return sign if sign in SIGN_SYMBOLS else None


def parse_members(raw_members: dict) -> dict[str, list[str]]:
    """Sign → names in zodiac order; accepts 牡羊 or 牡羊座, drops unknown signs."""
    members: dict[str, list[str]] = {}
    for raw_sign, names in raw_members.items():
        sign = normalize_sign(str(raw_sign))
        if sign is None or not isinstance(names, list):
            logger.warning("Skipping bad GROUP_MEMBERS entry", extra={"sign": raw_sign})
            continue
        members.setdefault(sign, []).extend(str(name) for name in names)
    return {sign: members[sign] for sign in ZODIAC_SIGNS if sign in members}


def _mask_in_actions_logs(members: dict[str, list[str]]) -> None:
    """Actions logs of a public repo are public, and a dry run prints the
    card; GitHub only masks the secret's whole value, not each name in it."""
    if os.getenv("GITHUB_ACTIONS") != "true":
        return
    for names in members.values():
        for name in names:
            print(f"::add-mask::{name}")


def read_group_members() -> dict[str, list[str]]:
    raw = os.getenv("GROUP_MEMBERS", "").strip()
    if not raw:
        return {}
    try:
        raw_members = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("GROUP_MEMBERS is not valid JSON")
        return {}
    if not isinstance(raw_members, dict):
        logger.warning("GROUP_MEMBERS must be a JSON object")
        return {}
    members = parse_members(raw_members)
    _mask_in_actions_logs(members)
    return members
