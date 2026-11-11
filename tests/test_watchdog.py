from __future__ import annotations

from datetime import date

from lunch_bot import watchdog
from lunch_bot.calendar_tw import DayKind
from lunch_bot.history import load_post_days, record_post_day, save_suggestion

DAY = date(2026, 11, 12)


def use_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(watchdog, "HISTORY_PATH", tmp_path / "history.json")
    monkeypatch.setattr(watchdog, "MORNING_POSTS_PATH", tmp_path / "morning.json")
    return tmp_path


def test_workday_without_posts_reports_both_cards(monkeypatch, tmp_path):
    use_data_dir(monkeypatch, tmp_path)
    assert watchdog.missing_cards(DAY, DayKind.WORKDAY) == ["早安卡", "午餐卡"]


def test_workday_with_both_posts_is_fine(monkeypatch, tmp_path):
    data = use_data_dir(monkeypatch, tmp_path)
    record_post_day(data / "morning.json", DAY)
    save_suggestion(data / "history.json", DAY, ["shop-1"])
    assert watchdog.missing_cards(DAY, DayKind.WORKDAY) == []


def test_days_off_are_never_reported(monkeypatch, tmp_path):
    use_data_dir(monkeypatch, tmp_path)
    assert watchdog.missing_cards(DAY, DayKind.WEEKEND) == []
    assert watchdog.missing_cards(DAY, DayKind.NATIONAL_HOLIDAY) == []


def test_recording_a_post_twice_keeps_one_entry(tmp_path):
    path = tmp_path / "morning.json"
    record_post_day(path, DAY)
    record_post_day(path, DAY)
    assert load_post_days(path) == ["2026-11-12"]
