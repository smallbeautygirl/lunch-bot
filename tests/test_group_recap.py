from __future__ import annotations

from datetime import date

import requests

from lunch_bot import group_recap
from lunch_bot.group_recap import fetch_group_recap, recap_lines
from lunch_bot.morning_card import HoroscopeContext, build_morning_card
from lunch_bot.recap_card import build_recap_card

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
    title, recap, scope = fetch_group_recap(TUESDAY)[0]
    assert (title, recap) == ("💬 **昨日群組回顧**", "大家聊了拉麵。")
    assert "客戶" in scope


def test_recap_written_for_another_day_is_not_shown(monkeypatch):
    serve(monkeypatch, {"date": "2026-11-23", "recap": "舊的回顧"})
    assert fetch_group_recap(TUESDAY) == []


def test_quiet_day_has_no_recap(monkeypatch):
    serve(monkeypatch, {"date": "2026-11-24", "recap": ""})
    assert fetch_group_recap(TUESDAY) == []


def test_without_a_token_nothing_is_fetched(monkeypatch):
    monkeypatch.delenv("PRIVATE_REPO_TOKEN", raising=False)
    monkeypatch.setattr(requests, "get", lambda *_, **__: 1 / 0)
    assert fetch_group_recap(TUESDAY) == []


def test_unreachable_private_repo_gives_no_recap(monkeypatch):
    def fail(*_: object, **__: object) -> None:
        raise requests.ConnectionError

    monkeypatch.setenv("PRIVATE_REPO_TOKEN", "token")
    monkeypatch.setattr(group_recap.requests, "get", fail)
    assert fetch_group_recap(TUESDAY) == []


def test_mondays_recap_is_titled_for_the_weekend():
    assert recap_lines(MONDAY, "x")[0] == "💬 **上週五到週末的群組回顧**"
    assert recap_lines(TUESDAY, "x")[0] == "💬 **昨日群組回顧**"


def test_each_group_section_is_its_own_shaded_box_on_the_card():
    card = build_morning_card(
        day=TUESDAY,
        taiex=None,
        overseas=[],
        fortunes=[],
        context=HoroscopeContext(),
        group_sections=[["💬 **昨日群組回顧**", "大家聊了拉麵。"], ["🏆 **榜**", "a"]],
    )
    boxes = [
        block
        for block in card["attachments"][0]["content"]["body"]
        if block.get("style") == "emphasis"
    ]
    assert [box["items"][0]["text"] for box in boxes] == [
        "💬 **昨日群組回顧**",
        "🏆 **榜**",
    ]
    assert boxes[0]["items"][1]["text"] == "大家聊了拉麵。"


def test_board_follows_the_recap_and_shows_alone_on_a_quiet_day(monkeypatch):
    board = {"title": "群組觀察（預覽）", "lines": ["🗣️ 話最多：小安"]}
    serve(monkeypatch, {"date": "2026-11-24", "recap": "", "board": board})
    assert fetch_group_recap(TUESDAY) == [["🏆 **群組觀察（預覽）**", "🗣️ 話最多：小安"]]


def test_resent_recap_card_is_titled_as_a_resend_and_holds_only_the_recap():
    card = build_recap_card(TUESDAY, [["💬 **昨日群組回顧**", "大家聊了拉麵。"]])
    title, box = card["attachments"][0]["content"]["body"]
    assert title["text"] == "💬 補發：11/24 群組回顧"
    assert box["items"][1]["text"] == "大家聊了拉麵。"
