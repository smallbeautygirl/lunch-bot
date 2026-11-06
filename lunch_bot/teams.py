"""Adaptive Card plumbing and delivery shared by the lunch and morning posts."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

import requests

from .config import HTTP_TIMEOUT_SECONDS, read_webhook_url

logger = logging.getLogger(__name__)


def text_block(text: str, **style: object) -> dict:
    return {"type": "TextBlock", "text": text, "wrap": True, **style}


def open_url_action(title: str, url: str) -> dict:
    return {"type": "Action.OpenUrl", "title": title, "url": url}


def wrap_card(
    body: list[dict],
    *,
    actions: list[dict],
    entities: list[dict] | None = None,
) -> dict:
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": body,
        "actions": actions,
        "msteams": {"width": "Full", "entities": entities or []},
    }
    return {
        "type": "message",
        "attachments": [
            {"contentType": "application/vnd.microsoft.card.adaptive", "content": card}
        ],
    }


def mark_as_test(payload: dict) -> dict:
    """Prefix the card title so manual runs are never mistaken for the real
    scheduled post."""
    body = payload["attachments"][0]["content"]["body"]
    body[0] = {**body[0], "text": f"[測試中] {body[0]['text']}"}
    return payload


def send_to_teams(payload: dict) -> None:
    webhook_url = read_webhook_url()
    if webhook_url is None:
        raise SystemExit("TEAMS_WEBHOOK_URL is not set")
    response = requests.post(webhook_url, json=payload, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    logger.info("Posted to Teams", extra={"status": response.status_code})


def parse_cli_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument(
        "--test",
        action="store_true",
        help="Post with a [測試中] title (and, for lunch, keep history untouched)",
    )
    return parser.parse_args()


def deliver(payload: dict, *, dry_run: bool, is_test: bool) -> None:
    if is_test:
        payload = mark_as_test(payload)
    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    send_to_teams(payload)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
