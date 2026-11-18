from __future__ import annotations

import json
from datetime import date

import requests

from lunch_bot import group_recap
from lunch_bot.group_recap import fetch_group_recap, recap_lines
from lunch_bot.morning_card import HoroscopeContext, build_morning_card

TUESDAY = date(2026, 11, 24)
MONDAY = date(2026, 11, 23)


class FakeResponse:
    def __init__(self, saved: dict) -> None:
        self.saved = saved

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.saved


def serve(monkeypatch, saved: dict) -> None:
    monkeypatch.setenv("PRIVATE_REPO_TOKEN", "token")
    monkeypatch.setattr(requests, "get", lambda *_, **__: FakeResponse(saved))


def test_todays_recap_is_returned(monkeypatch):
    serve(monkeypatch, {"date": "2026-11-24", "recap": "大家聊了拉麵。"})
    assert fetch_group_recap(TUESDAY) == "大家聊了拉麵。"


def test_recap_written_for_another_day_is_not_shown(monkeypatch):
    serve(monkeypatch, {"date": "2026-11-23", "recap": "舊的回顧"})
    assert fetch_group_recap(TUESDAY) is None


def test_quiet_day_has_no_recap(monkeypatch):
    serve(monkeypatch, {"date": "2026-11-24", "recap": ""})
    assert fetch_group_recap(TUESDAY) is None


def test_without_a_token_nothing_is_fetched(monkeypatch):
    monkeypatch.delenv("PRIVATE_REPO_TOKEN", raising=False)
    monkeypatch.setattr(requests, "get", lambda *_, **__: 1 / 0)
    assert fetch_group_recap(TUESDAY) is None


def test_unreachable_private_repo_gives_no_recap(monkeypatch):
    def fail(*_: object, **__: object) -> None:
        raise requests.ConnectionError

    monkeypatch.setenv("PRIVATE_REPO_TOKEN", "token")
    monkeypatch.setattr(group_recap.requests, "get", fail)
    assert fetch_group_recap(TUESDAY) is None


def test_mondays_recap_is_titled_for_the_weekend():
    assert recap_lines(MONDAY, "x")[0] == "💬 **上週五到週末的群組回顧**"
    assert recap_lines(TUESDAY, "x")[0] == "💬 **昨日群組回顧**"


def test_morning_card_shows_the_recap_when_there_is_one():
    context = HoroscopeContext(members={}, sources={}, tang=None, mafalda=None)
    card = build_morning_card(
        day=TUESDAY,
        taiex=None,
        overseas=[],
        fortunes=[],
        context=context,
        recap=recap_lines(TUESDAY, "大家聊了拉麵。"),
    )
    assert "昨日群組回顧**\\n\\n大家聊了拉麵。" in json.dumps(card, ensure_ascii=False)
