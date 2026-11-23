"""must-tui works in UTC throughout. tests/conftest.py runs every test with a non-UTC local timezone (Brussels), so a
local-time conversion anywhere shows up here as an offset of one or two hours."""

import asyncio
import datetime as dt
import re
import time

import plotext
import pytest

from must_tui import must
from must_tui.must_app import TimeRangePlotter, time_axis_ticks
from must_tui.time_range_input import parse_datetime, utc_now, utc_timestamp
from must_tui.time_ranges import default_time_range, time_range_presets

UTC = dt.timezone.utc


def test_the_tests_really_run_in_a_non_utc_local_timezone():
    if not hasattr(time, "tzset"):
        pytest.skip("time.tzset() is Unix only")
    summer = dt.datetime(2026, 7, 1, 12, tzinfo=UTC)
    assert summer.astimezone().utcoffset() == dt.timedelta(hours=2)


def test_utc_now_is_naive_utc():
    before = dt.datetime.now(UTC).replace(tzinfo=None)
    now = utc_now()
    after = dt.datetime.now(UTC).replace(tzinfo=None)

    assert now.tzinfo is None
    assert before <= now <= after


def test_utc_timestamp_takes_a_naive_datetime_as_utc():
    assert utc_timestamp(dt.datetime(1970, 1, 1, 1)) == 3600.0


def test_now_and_today_are_utc_by_default():
    assert abs(parse_datetime("now") - utc_now()) < dt.timedelta(seconds=2)
    assert parse_datetime("today") == utc_now().replace(hour=0, minute=0, second=0, microsecond=0)


def test_presets_and_the_default_range_end_at_utc_now():
    for time_range in [default_time_range(), *(time_range for _, time_range in time_range_presets()[:6])]:
        assert abs(time_range.end - utc_now()) < dt.timedelta(seconds=2)


def test_sample_timestamps_from_must_are_naive_utc():
    # 2026-10-21 12:00:10 UTC, in summer time: a local-time conversion would give 14:00:10 in Brussels
    epoch_ms = int(dt.datetime(2026, 10, 21, 12, 0, 10, tzinfo=UTC).timestamp() * 1000)
    data = {"content": [{"data": [{"date": str(epoch_ms), "value": 1.5}]}]}

    timestamps, values = must.get_raw_data_with_timestamp(data)

    assert timestamps == [dt.datetime(2026, 10, 21, 12, 0, 10)]
    assert values == [1.5]


def test_time_axis_ticks():
    start, end = dt.datetime(2026, 10, 21, 12, 0, 10), dt.datetime(2026, 10, 21, 13, 0, 10)

    positions, labels = time_axis_ticks(start, end)

    assert labels == [
        "2026-10-21 12:00:10", "2026-10-21 12:15:10", "2026-10-21 12:30:10", "2026-10-21 12:45:10",
        "2026-10-21 13:00:10",
    ]
    assert positions == [utc_timestamp(start) + 900 * index for index in range(5)]


def test_time_axis_ticks_for_an_empty_range():
    moment = dt.datetime(2026, 1, 1)

    assert time_axis_ticks(moment, moment) == ([utc_timestamp(moment)], ["2026-01-01 00:00:00"])


def _render(plotter: TimeRangePlotter) -> str:
    return plotext.uncolorize(plotter.plt.build())


def test_tui_plot_labels_and_data_match_the_utc_time_range():
    # Regression test: in summer time in Brussels, the axis of a 12:00:10 - 13:00:10 range was labelled
    # 14:00:10 - 15:00:10 (plotext's own date axis writes its labels in local time), and the samples were drawn
    # two hours outside it, leaving the plot empty (they were converted from MUST's epoch ms to local time).
    start, end = dt.datetime(2026, 10, 21, 12, 0, 10), dt.datetime(2026, 10, 21, 13, 0, 10)
    epoch_ms = [int((start + dt.timedelta(minutes=m)).replace(tzinfo=UTC).timestamp() * 1000) for m in range(61)]
    timestamps, values = must.get_raw_data_with_timestamp(
        {"content": [{"data": [{"date": str(ms), "value": float(index)} for index, ms in enumerate(epoch_ms)]}]}
    )

    plotter = TimeRangePlotter(must.MustContext())
    plotter.set_xlimits(start, end)
    asyncio.run(plotter.update("PAR_X", timestamps, values, None))
    rendered = _render(plotter)

    # plotext drops labels that would overlap at its (80-column) default size, so which of the five ticks get a
    # label varies; every label shown must be one of them, though, and in UTC
    shown = re.findall(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", rendered)
    assert len(shown) >= 2
    assert set(shown) <= set(time_axis_ticks(start, end)[1])
    # the first sample is in the canvas's first column, the last one in its last column
    canvas = [re.sub(r"^[^┤│]*[┤│]", "", row.rstrip())[:-1] for row in rendered.splitlines() if row.rstrip().endswith("│")]
    assert canvas and all(len(row) == len(canvas[0]) for row in canvas)
    assert any(row.startswith("•") for row in canvas)
    assert any(row.endswith("•") for row in canvas)
