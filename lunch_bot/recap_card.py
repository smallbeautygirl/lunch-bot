"""Resend the group recap on its own, for a morning whose card went out
before the recap was ready.

python -m lunch_bot.recap_card --note "補發：…"
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime

from .config import TAIPEI
from .group_recap import fetch_group_recap
from .morning_card import shaded_section
from .teams import configure_logging, deliver, text_block, wrap_card

logger = logging.getLogger(__name__)


def build_recap_card(day: date, sections: list[list[str]]) -> dict:
    title = f"💬 補發：{day.month}/{day.day} 群組回顧"
    body = [text_block(title, size="Large", weight="Bolder")]
    body += [shaded_section(lines) for lines in sections]
    return wrap_card(body, actions=[])


def run() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Resend the group recap")
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    day = datetime.now(TAIPEI).date()
    sections = fetch_group_recap(day)
    if not sections:
        raise SystemExit("No recap for today to resend")
    card = build_recap_card(day, sections)
    deliver(card, dry_run=False, is_test=False, note=args.note or None)


if __name__ == "__main__":
    run()
