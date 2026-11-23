import datetime as dt
import json

import pytest

import must_tui.must_app as must_app
from must_tui.time_range_input import TimeRange
from must_tui.time_ranges import (
    MAX_RECENT_TIME_RANGES,
    add_recent_time_range,
    data_range_presets,
    default_time_range,
    get_time_range_history_path,
    load_recent_time_ranges,
    save_recent_time_ranges,
    time_range_presets,
)

NOW = dt.datetime(2026, 11, 23, 9, 30, 15, 123456)


def _range(day: int) -> TimeRange:
    return TimeRange(dt.datetime(2026, 1, day), dt.datetime(2026, 1, day, 12))


def test_default_time_range_is_the_last_day_up_to_now_to_the_second():
    assert default_time_range(NOW) == TimeRange(dt.datetime(2026, 11, 22, 9, 30, 15), dt.datetime(2026, 11, 23, 9, 30, 15))


def test_time_range_presets():
    presets = dict(time_range_presets(NOW))
    now = NOW.replace(microsecond=0)

    assert list(presets) == [
        "Last hour", "Last 6 hours", "Last 24 hours", "Last 3 days", "Last 7 days", "Last 30 days", "Today", "Yesterday"
    ]
    assert presets["Last hour"] == TimeRange(now - dt.timedelta(hours=1), now)
    assert presets["Last 30 days"] == TimeRange(now - dt.timedelta(days=30), now)
    assert presets["Today"] == TimeRange(dt.datetime(2026, 11, 23), now)
    assert presets["Yesterday"] == TimeRange(dt.datetime(2026, 11, 22), dt.datetime(2026, 11, 23))


def test_time_range_presets_leave_out_an_empty_today_at_midnight():
    labels = [label for label, _ in time_range_presets(dt.datetime(2026, 11, 23))]

    assert "Today" not in labels
    assert "Yesterday" in labels


def test_add_recent_time_range_moves_to_front_without_duplicates_and_caps_the_length():
    recent = [_range(day) for day in range(1, MAX_RECENT_TIME_RANGES + 1)]

    assert add_recent_time_range(recent, _range(3))[:3] == [_range(3), _range(1), _range(2)]
    assert len(add_recent_time_range(recent, _range(3))) == MAX_RECENT_TIME_RANGES
    assert add_recent_time_range(recent, _range(20)) == [_range(20), *recent[:-1]]


def test_history_path_follows_xdg_cache_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    assert get_time_range_history_path() == tmp_path / "must-tui" / "time_ranges.json"


def test_recent_time_ranges_round_trip(tmp_path):
    path = tmp_path / "sub" / "time_ranges.json"
    recent = [_range(2), _range(1)]

    assert save_recent_time_ranges(recent, path)
    assert load_recent_time_ranges(path) == recent
    assert not path.with_name("time_ranges.json.tmp").exists()


@pytest.mark.parametrize("content", ["", "not json", "[]", '{"recent": 5}', '{"other": []}'])
def test_unusable_history_files_give_no_recent_ranges(tmp_path, content):
    path = tmp_path / "time_ranges.json"
    path.write_text(content)

    assert load_recent_time_ranges(path) == []


def test_invalid_history_entries_are_skipped(tmp_path):
    path = tmp_path / "time_ranges.json"
    path.write_text(json.dumps({"recent": [
        {"start": "2026-01-02 00:00:00", "end": "2026-01-01 00:00:00"},  # start after end
        {"start": "garbage", "end": "2026-01-01 00:00:00"},
        {"start": "2026-01-01 00:00:00"},
        "not a dict",
        {"start": "2026-01-01 00:00:00", "end": "2026-01-01 12:00:00"},
        {"start": "2026-01-01 00:00:00", "end": "2026-01-01 12:00:00"},  # duplicate
    ]}))

    assert load_recent_time_ranges(path) == [_range(1)]


def test_a_missing_history_file_gives_no_recent_ranges(tmp_path):
    assert load_recent_time_ranges(tmp_path / "nope.json") == []


def test_saving_into_an_unwritable_place_reports_failure_instead_of_raising(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("")

    assert save_recent_time_ranges([_range(1)], blocker / "time_ranges.json") is False


def test_app_starts_with_the_most_recent_range_or_the_last_day():
    assert must_app.MUSTApp().time_range.end - must_app.MUSTApp().time_range.start == dt.timedelta(days=1)

    save_recent_time_ranges([_range(5), _range(4)])  # into the per-test cache dir (tests/conftest.py)
    app = must_app.MUSTApp()

    assert app.time_range == _range(5)
    assert app.recent_time_ranges == [_range(5), _range(4)]


def test_data_range_presets_end_at_the_last_sample_and_are_not_clamped_to_the_first():
    data_range = TimeRange(dt.datetime(2026, 1, 1, 6), dt.datetime(2026, 1, 1, 12))
    presets = dict(data_range_presets(data_range))

    assert list(presets) == [
        "Last hour of data", "Last 6 hours of data", "Last 24 hours of data",
        "Last 3 days of data", "Last 7 days of data", "Last 30 days of data",
    ]
    assert presets["Last hour of data"] == TimeRange(dt.datetime(2026, 1, 1, 11), dt.datetime(2026, 1, 1, 12))
    assert presets["Last 6 hours of data"] == data_range
    # more than the parameter has: starts before its first sample, rather than collapsing onto the data range
    assert presets["Last 24 hours of data"] == TimeRange(dt.datetime(2025, 12, 31, 12), dt.datetime(2026, 1, 1, 12))
