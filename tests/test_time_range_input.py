import asyncio
import datetime as dt

import pytest
from textual import on
from textual.app import App
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Input, OptionList

import must_tui.must_app as must_app
from must_tui.must_app import ParameterMetadata
from must_tui.dialogs import TimeRangeDialog
from must_tui.time_range_input import (
    TimeRange,
    TimeRangeInput,
    format_datetime,
    parse_datetime,
    relative_anchor,
    utc_now,
)
from must_tui.time_ranges import load_recent_time_ranges

START = dt.datetime(2025, 12, 2)
END = dt.datetime(2025, 12, 5)


NOW = dt.datetime(2026, 10, 11, 9, 30, 15, 123456)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2025-10-01 13:45:07", dt.datetime(2025, 10, 1, 13, 45, 7)),
        ("2025-10-01 13:45", dt.datetime(2025, 10, 1, 13, 45)),
        ("2025-10-01", dt.datetime(2025, 10, 1)),
        ("2025-10-01T13:45:07", dt.datetime(2025, 10, 1, 13, 45, 7)),
        ("  2025-03-09   08:00  ", dt.datetime(2025, 3, 9, 8)),
        ("NOW", dt.datetime(2026, 10, 11, 9, 30, 15)),
        ("today", dt.datetime(2026, 10, 11)),
        ("TODAY", dt.datetime(2026, 10, 11)),
        ("yesterday", dt.datetime(2026, 10, 10)),
        ("tomorrow", dt.datetime(2026, 10, 12)),
        ("now-6h", dt.datetime(2026, 10, 11, 3, 30, 15)),
        ("now+6h", dt.datetime(2026, 10, 11, 15, 30, 15)),
        ("-2h30m", dt.datetime(2026, 10, 11, 7, 0, 15)),
        ("- 2h 30m", dt.datetime(2026, 10, 11, 7, 0, 15)),
        ("now - 1d2h3m4s", dt.datetime(2026, 10, 10, 7, 27, 11)),
        ("yesterday-3h", dt.datetime(2026, 10, 9, 21)),
        ("tomorrow+1w", dt.datetime(2026, 10, 19)),
        ("-1W", dt.datetime(2026, 10, 4, 9, 30, 15)),
    ],
)
def test_parse_datetime_accepts(text, expected):
    assert parse_datetime(text, now=NOW) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "2025-13-01",
        "2025-11-31",
        "2025-10",
        "2025-10-01 25:00",
        "0999-01-01",
        "0025-10-01",
        "now-",
        "now-6",
        "now-6x",
        "6h",
        "now 6h",
        "yesterdayish",
    ],
)
def test_parse_datetime_rejects(text):
    with pytest.raises(ValueError, match="not a valid date-time"):
        parse_datetime(text, now=NOW)


@pytest.mark.parametrize("text", ["-999999999d", "+999999999w"])
def test_parse_datetime_rejects_relative_out_of_range(text):
    with pytest.raises(ValueError, match="out of range"):
        parse_datetime(text, now=NOW)


RANGE = TimeRange(dt.datetime(2025, 12, 2, 8), dt.datetime(2025, 12, 5, 20, 30))


@pytest.mark.parametrize(
    "text, expected",
    [
        ("start", dt.datetime(2025, 12, 2, 8)),
        ("END", dt.datetime(2025, 12, 5, 20, 30)),
        ("end-6h", dt.datetime(2025, 12, 5, 14, 30)),
        ("end - 1d 30m", dt.datetime(2025, 12, 4, 20)),
        ("start+90m", dt.datetime(2025, 12, 2, 9, 30)),
        ("Start+1w", dt.datetime(2025, 12, 9, 8)),
        # the existing anchors are unaffected by a given range
        ("now-6h", dt.datetime(2026, 10, 11, 3, 30, 15)),
        ("-2h30m", dt.datetime(2026, 10, 11, 7, 0, 15)),
    ],
)
def test_parse_datetime_accepts_start_and_end_anchors_with_a_range(text, expected):
    assert parse_datetime(text, now=NOW, time_range=RANGE) == expected


@pytest.mark.parametrize("text", ["start", "end-6h", "start+1d"])
def test_parse_datetime_rejects_start_and_end_without_a_range(text):
    with pytest.raises(ValueError, match="only be used in the time range fields"):
        parse_datetime(text, now=NOW)


@pytest.mark.parametrize("text", ["starting", "ends", "end6h", "end-", "end-6x"])
def test_parse_datetime_rejects_malformed_start_and_end_expressions(text):
    with pytest.raises(ValueError, match="not a valid date-time"):
        parse_datetime(text, now=NOW, time_range=RANGE)


@pytest.mark.parametrize(
    "text, expected",
    [("end-6h", "end"), (" START + 1d ", "start"), ("-2h", "now"), ("today", "today"), ("2025-01-01", None)],
)
def test_relative_anchor(text, expected):
    assert relative_anchor(text) == expected


class _Host(App):
    def __init__(self):
        super().__init__()
        self.changes = []

    def compose(self):
        yield TimeRangeInput(START, END, id="time-range")

    @on(TimeRangeInput.Changed, "#time-range")
    def changed(self, event):
        self.changes.append(event.time_range)


async def _type_into(pilot, field_id, text, confirm="enter"):
    field = pilot.app.query_one(field_id, Input)
    field.focus()
    await pilot.pause()
    field.value = ""
    await pilot.press(*text)
    await pilot.pause()
    changes_before_confirm = list(pilot.app.changes)
    await pilot.press(confirm)
    await pilot.pause()
    return field, changes_before_confirm


def _run(test):
    async def main():
        app = _Host()
        async with app.run_test(size=(120, 10)) as pilot:
            await pilot.pause()
            await test(app, pilot)

    asyncio.run(main())


def test_typing_sends_nothing_until_enter_then_one_change():
    async def test(app, pilot):
        _, before_enter = await _type_into(pilot, "#time-range-start", "2025-10-01 06:00")
        assert before_enter == []
        assert app.changes == [TimeRange(dt.datetime(2025, 10, 1, 6), END)]
        # the field is normalized to the full format
        assert app.query_one("#time-range-start", Input).value == "2025-10-01 06:00:00"

    _run(test)


def test_leaving_the_field_also_applies_it_but_only_once():
    async def test(app, pilot):
        await _type_into(pilot, "#time-range-end", "2025-12-04", confirm="enter")
        await pilot.press("tab")
        await pilot.pause()
        assert app.changes == [TimeRange(START, dt.datetime(2025, 12, 4))]

    _run(test)


def test_invalid_text_is_marked_and_keeps_the_range():
    async def test(app, pilot):
        field, _ = await _type_into(pilot, "#time-range-start", "2025-11-31")
        assert app.changes == []
        assert field.has_class("-invalid")
        assert app.query_one(TimeRangeInput).time_range == TimeRange(START, END)
        await pilot.press("backspace")  # editing clears the mark
        await pilot.pause()
        assert not field.has_class("-invalid")

    _run(test)


def test_start_after_end_is_rejected():
    async def test(app, pilot):
        field, _ = await _type_into(pilot, "#time-range-start", "2025-12-06")
        assert app.changes == []
        assert field.has_class("-invalid")

    _run(test)


def test_lock_keeps_the_duration():
    async def test(app, pilot):
        app.query_one("#time-range-lock", Checkbox).value = True
        await _type_into(pilot, "#time-range-start", "2025-10-01")
        assert app.changes == [TimeRange(dt.datetime(2025, 10, 1), dt.datetime(2025, 10, 4))]
        assert app.query_one("#time-range-end", Input).value == "2025-10-04 00:00:00"

    _run(test)


def test_lock_beyond_the_last_year_is_rejected():
    async def test(app, pilot):
        app.query_one("#time-range-lock", Checkbox).value = True
        field, _ = await _type_into(pilot, "#time-range-start", "9999-12-31")
        assert app.changes == []
        assert field.has_class("-invalid")

    _run(test)


def test_end_anchor_in_the_start_field():
    async def test(app, pilot):
        await _type_into(pilot, "#time-range-start", "end-6h")
        assert app.changes == [TimeRange(END - dt.timedelta(hours=6), END)]
        assert app.query_one("#time-range-start", Input).value == format_datetime(END - dt.timedelta(hours=6))

    _run(test)


def test_start_anchor_in_the_end_field():
    async def test(app, pilot):
        await _type_into(pilot, "#time-range-end", "start+90m")
        assert app.changes == [TimeRange(START, START + dt.timedelta(minutes=90))]

    _run(test)


def test_an_anchor_on_the_other_end_keeps_that_end_even_when_locked():
    async def test(app, pilot):
        app.query_one("#time-range-lock", Checkbox).value = True
        await _type_into(pilot, "#time-range-start", "end-6h")
        await _type_into(pilot, "#time-range-end", "start+1h")
        assert app.changes == [
            TimeRange(END - dt.timedelta(hours=6), END),
            TimeRange(END - dt.timedelta(hours=6), END - dt.timedelta(hours=5)),
        ]

    _run(test)


def test_an_anchor_on_the_same_end_with_lock_shifts_the_whole_range():
    async def test(app, pilot):
        app.query_one("#time-range-lock", Checkbox).value = True
        await _type_into(pilot, "#time-range-start", "start+1d")
        assert app.changes == [TimeRange(START + dt.timedelta(days=1), END + dt.timedelta(days=1))]

    _run(test)


def test_start_anchor_in_the_start_field_beyond_the_end_is_rejected():
    async def test(app, pilot):
        field, _ = await _type_into(pilot, "#time-range-start", "end+1h")
        assert app.changes == []
        assert field.has_class("-invalid")

    _run(test)


def test_stepping_an_end_anchored_expression_materializes_it_first():
    async def test(app, pilot):
        field = app.query_one("#time-range-start", Input)
        field.focus()
        await pilot.pause()
        field.value = "end-6h"
        field.cursor_position = 2  # year segment (the raw text is too short to put the cursor on the hour)
        await pilot.press("up")
        await pilot.pause()
        # resolved against the range's end first (END - 6h), then Up increments the year under the cursor
        assert field.value == format_datetime((END - dt.timedelta(hours=6)).replace(year=END.year + 1))
        assert app.changes == []

    _run(test)


def test_confirming_an_unchanged_value_sends_nothing():
    async def test(app, pilot):
        await _type_into(pilot, "#time-range-start", "2025-12-02 00:00")
        assert app.changes == []

    _run(test)


def test_escape_defocuses_the_field():
    async def test(app, pilot):
        field = app.query_one("#time-range-start", Input)
        field.focus()
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.focused is None

    _run(test)


def test_escape_commits_a_pending_valid_edit_like_a_blur():
    async def test(app, pilot):
        field, before_escape = await _type_into(pilot, "#time-range-start", "2025-10-01", confirm="escape")
        assert before_escape == []
        assert app.changes == [TimeRange(dt.datetime(2025, 10, 1), END)]
        assert app.screen.focused is None

    _run(test)


async def _step(pilot, field_id, cursor, key):
    field = pilot.app.query_one(field_id, Input)
    field.focus()
    field.cursor_position = cursor
    await pilot.pause()
    changes_before = list(pilot.app.changes)
    await pilot.press(key)
    await pilot.pause()
    return field, changes_before


def test_up_down_step_year_without_applying():
    async def test(app, pilot):
        field, before = await _step(pilot, "#time-range-start", 2, "up")
        assert before == []
        assert field.value == "2026-12-02 00:00:00"
        assert field.cursor_position == 2
        assert app.changes == []  # stepping alone never applies

        await pilot.press("down")
        await pilot.pause()
        assert field.value == "2025-12-02 00:00:00"

    _run(test)


@pytest.mark.parametrize(
    "cursor, expected_up, expected_down",
    [
        (6, "2026-01-02 00:00:00", "2025-11-02 00:00:00"),  # month
        (9, "2025-12-03 00:00:00", "2025-12-01 00:00:00"),  # day
        (12, "2025-12-02 01:00:00", "2025-12-01 23:00:00"),  # hour
        (15, "2025-12-02 00:01:00", "2025-12-01 23:59:00"),  # minute
        (18, "2025-12-02 00:00:01", "2025-12-01 23:59:59"),  # second
    ],
)
def test_up_down_step_the_segment_under_the_cursor(cursor, expected_up, expected_down):
    async def test(app, pilot):
        field, _ = await _step(pilot, "#time-range-start", cursor, "up")
        assert field.value == expected_up
        field.cursor_position = cursor
        await pilot.press("down")
        await pilot.press("down")
        await pilot.pause()
        assert field.value == expected_down
        assert app.changes == []

    _run(test)


def test_up_clamps_to_the_last_day_of_a_shorter_month():
    async def test(app, pilot):
        field = app.query_one("#time-range-start", Input)
        field.value = "2025-01-31 00:00:00"
        field.focus()
        field.cursor_position = 6
        await pilot.pause()
        await pilot.press("up")
        await pilot.pause()
        assert field.value == "2025-02-28 00:00:00"

    _run(test)


def test_up_clamps_a_leap_day_on_a_non_leap_year():
    async def test(app, pilot):
        field = app.query_one("#time-range-start", Input)
        field.value = "2024-02-29 00:00:00"
        field.focus()
        field.cursor_position = 2
        await pilot.pause()
        await pilot.press("up")
        await pilot.pause()
        assert field.value == "2025-02-28 00:00:00"

    _run(test)


def test_stepping_past_the_year_bounds_is_a_no_op():
    async def test(app, pilot):
        field = app.query_one("#time-range-start", Input)
        field.value = "9999-12-31 23:59:59"
        field.focus()
        field.cursor_position = 2
        await pilot.pause()
        await pilot.press("up")
        await pilot.pause()
        assert field.value == "9999-12-31 23:59:59"

        field.value = "1000-01-01 00:00:00"
        field.cursor_position = 2
        await pilot.press("down")
        await pilot.pause()
        assert field.value == "1000-01-01 00:00:00"

    _run(test)


def test_stepping_a_day_rolls_over_into_the_next_year():
    async def test(app, pilot):
        field = app.query_one("#time-range-start", Input)
        field.value = "2025-12-31 23:59:59"
        field.focus()
        field.cursor_position = 9
        await pilot.pause()
        await pilot.press("up")
        await pilot.pause()
        assert field.value == "2026-01-01 23:59:59"

    _run(test)


def test_stepping_invalid_text_does_nothing():
    async def test(app, pilot):
        field = app.query_one("#time-range-start", Input)
        field.value = "2025-11-31"
        field.focus()
        field.cursor_position = 9
        await pilot.pause()
        await pilot.press("up")
        await pilot.pause()
        assert field.value == "2025-11-31"
        assert app.changes == []

    _run(test)


def test_stepping_relative_text_materializes_it_first():
    async def test(app, pilot):
        field = app.query_one("#time-range-start", Input)
        field.value = "today"
        field.focus()
        field.cursor_position = 2  # year segment
        await pilot.pause()
        today = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        await pilot.press("up")
        await pilot.pause()
        # "today" (this year, midnight) is materialized first, then Up increments the year under the cursor
        assert field.value == format_datetime(today.replace(year=today.year + 1))
        assert app.changes == []

    _run(test)


def test_a_stepped_value_is_applied_on_enter():
    async def test(app, pilot):
        field, _ = await _step(pilot, "#time-range-start", 9, "up")  # day
        assert field.value == "2025-12-03 00:00:00"
        assert app.changes == []

        await pilot.press("enter")
        await pilot.pause()
        assert app.changes == [TimeRange(dt.datetime(2025, 12, 3), END)]

    _run(test)


def test_up_down_also_steps_the_end_field():
    async def test(app, pilot):
        field, before = await _step(pilot, "#time-range-end", 9, "up")  # day
        assert before == []
        assert field.value == "2025-12-06 00:00:00"
        assert app.changes == []

    _run(test)


def test_set_time_range_from_code_sends_nothing():
    async def test(app, pilot):
        widget = app.query_one(TimeRangeInput)
        widget.set_time_range(TimeRange(dt.datetime(2025, 1, 1), dt.datetime(2025, 1, 2)))
        await pilot.pause()
        assert app.changes == []
        assert app.query_one("#time-range-start", Input).value == "2025-01-01 00:00:00"

    _run(test)


class _FakePlotter:
    def __init__(self, series):
        self.labels = [name for name, _, _ in series]
        self.time = [t for _, t, _ in series]
        self.data = [v for _, _, v in series]
        self.fetched_ranges = [(None, False) for _ in series]
        self.xlimits = self.ylimits = None

    def clear_plot(self):
        self.labels, self.time, self.data, self.fetched_ranges = [], [], [], []

    def set_xlimits(self, start, end):
        self.xlimits = (start, end)

    def set_ylimits(self, ymin, ymax):
        self.ylimits = (ymin, ymax)

    async def update(self, name, timestamps, values, time_range, truncated=False):
        self.labels.append(name)
        self.time.append(timestamps)
        self.data.append(values)
        self.fetched_ranges.append((time_range, truncated))


def _app_for_reload(monkeypatch, plotted, server_data, during_fetch=None, truncated_names=frozenset()):
    app = must_app.MUSTApp()
    app.time_range = TimeRange(dt.datetime(2025, 10, 1), dt.datetime(2025, 10, 2))
    app.plot_widget = _FakePlotter(plotted)
    app.notifications = []
    app.notify = lambda message, **kwargs: app.notifications.append(message)
    requests = []

    async def fake_get_parameter_data(_ctx, _provider, name, start, end, paginated=False, truncated=None):
        requests.append((name, start, end))
        if during_fetch:
            during_fetch(app)
        if name in truncated_names and truncated is not None:
            truncated.append(True)
        if name in server_data:
            yield {"content": [{"data": [{"date": str(ms), "value": v} for ms, v in server_data[name]]}]}

    monkeypatch.setattr(must_app, "get_parameter_data", fake_get_parameter_data)
    return app, requests


def _ms(*args):
    return int(dt.datetime(*args, tzinfo=dt.timezone.utc).timestamp() * 1000)  # MUST's epoch ms; must-tui is UTC


def test_reload_fetches_every_plotted_parameter_once_for_the_new_range(monkeypatch):
    old = [dt.datetime(2025, 12, 2)]
    plotted = [("A", old, [1.0]), ("B", old, [2.0]), ("A", old, [1.0])]
    server_data = {"A": [(_ms(2025, 10, 1, 12), 5.0)], "B": [(_ms(2025, 10, 1, 13), 7.0)]}
    app, requests = _app_for_reload(monkeypatch, plotted, server_data)

    asyncio.run(app._reload_plotted_parameters())

    period = ("2025-10-01 00:00:00", "2025-10-02 00:00:00")
    assert requests == [("A", *period), ("B", *period)]
    assert app.plot_widget.labels == ["A", "B"]
    assert app.plot_widget.data == [[5.0], [7.0]]
    assert app.plot_widget.xlimits == (app.time_range.start, app.time_range.end)
    assert app.plot_widget.ylimits is None  # auto-scaled: no manual Y range was locked
    assert app.notifications[0].startswith(f"Reloading 2 plotted parameter(s) for {period[0]} – {period[1]}")
    assert app.notifications[-1].startswith("Reloaded 2 of 2 parameter(s)")


def test_reload_removes_parameters_without_data_and_says_so(monkeypatch):
    old = [dt.datetime(2025, 12, 2)]
    app, _ = _app_for_reload(
        monkeypatch, [("A", old, [1.0]), ("B", old, [2.0])], {"A": [(_ms(2025, 10, 1, 12), 5.0)]}
    )

    asyncio.run(app._reload_plotted_parameters())

    assert app.plot_widget.labels == ["A"]
    assert "No data in this range for: B" in app.notifications[-1]


def test_reload_with_nothing_plotted_does_nothing(monkeypatch):
    app, requests = _app_for_reload(monkeypatch, [], {})

    asyncio.run(app._reload_plotted_parameters())

    assert requests == [] and app.notifications == []


def test_reload_respects_clear_and_selection_during_the_fetch(monkeypatch):
    old = [dt.datetime(2025, 12, 2)]
    new = [dt.datetime(2025, 10, 1, 12)]
    server_data = {"A": [(_ms(2025, 10, 1, 12), 5.0)]}

    def clear_then_select_c(app):
        app.plot_widget.clear_plot()
        plot = app.plot_widget
        plot.labels, plot.time, plot.data, plot.fetched_ranges = ["C"], [new], [[9.0]], [(None, False)]

    app, _ = _app_for_reload(monkeypatch, [("A", old, [1.0])], server_data, during_fetch=clear_then_select_c)

    asyncio.run(app._reload_plotted_parameters())

    # A was cleared by the user while it was being fetched, C was selected meanwhile
    assert app.plot_widget.labels == ["C"]
    assert app.plot_widget.data == [[9.0]]


def test_reload_notifies_when_a_parameters_data_is_truncated(monkeypatch):
    old = [dt.datetime(2025, 12, 2)]
    server_data = {"A": [(_ms(2025, 10, 1, 12), 5.0)]}
    app, _ = _app_for_reload(monkeypatch, [("A", old, [1.0])], server_data, truncated_names={"A"})

    asyncio.run(app._reload_plotted_parameters())

    assert app.plot_widget.labels == ["A"]  # the partial data is still plotted, just flagged
    assert "Only partial data" in app.notifications[-1]
    assert "A" in app.notifications[-1]


class _FakeMainScreen(Screen):
    """A stand-in for MainScreen with just the widgets `choose_time_range` needs."""

    def compose(self):
        yield ParameterMetadata()
        yield Button("Range…", id="bt-time-range")
        yield TimeRangeInput(START, END, id="time-range")


def _app_for_time_range_dialog(monkeypatch):
    async def fake_initialize(self):
        self.install_screen(_FakeMainScreen(), name="main")
        self.push_screen("main")
        self.time_range = TimeRange(START, END)

    monkeypatch.setattr(must_app.MUSTApp, "_initialize_and_show_main_screen", fake_initialize)
    return must_app.MUSTApp()


async def _open_time_range_dialog(app, pilot, metadata=None, via_key=False):
    while not isinstance(app.screen, _FakeMainScreen):
        await pilot.pause(0.05)
    if metadata is not None:
        await app.screen.query_one(ParameterMetadata).update_metadata("PAR_X", metadata)
    if via_key:
        await pilot.press("f6")
    else:
        app.screen.query_one("#bt-time-range", Button).press()
    while not isinstance(app.screen, TimeRangeDialog):
        await pilot.pause(0.05)
    return app.screen


async def _pick_time_range_option(app, option_id=None, metadata=None, via_key=False):
    """Open the dialog, select `option_id` (or press Escape when None), and return (dialog options, field text)."""

    async with app.run_test(size=(120, 40)) as pilot:
        dialog = await _open_time_range_dialog(app, pilot, metadata, via_key)
        option_list = dialog.query_one(OptionList)
        options = [option_list.get_option_at_index(i) for i in range(option_list.option_count)]
        if option_id is None:
            await pilot.press("escape")
        else:
            option_list.highlighted = option_list.get_option_index(option_id)
            await pilot.press("enter")
        while isinstance(app.screen, TimeRangeDialog):
            await pilot.pause(0.05)
        await pilot.pause()
        return options, app.screen.query_one("#time-range-start", Input).value


def test_time_range_dialog_applies_the_parameters_data_range(monkeypatch):
    app = _app_for_time_range_dialog(monkeypatch)
    metadata = {"first-sample": "2024-01-01 00:00:00", "last-sample": "2024-06-01 12:00:00"}

    _, start_field_value = asyncio.run(_pick_time_range_option(app, "data-range", metadata))

    assert app.time_range == TimeRange(dt.datetime(2024, 1, 1), dt.datetime(2024, 6, 1, 12))
    assert start_field_value == "2024-01-01 00:00:00"
    # regression guard: set_xlimits() must not crash plotext on the very first-ever call (before any replot())
    assert app.plot_widget.xlimits == (dt.datetime(2024, 1, 1), dt.datetime(2024, 6, 1, 12))


@pytest.mark.parametrize(
    "metadata, reason",
    [
        (None, "Select a parameter"),
        ({"first-sample": "2024-06-01 00:00:00", "last-sample": "2024-01-01 00:00:00"}, "is not before its last"),
    ],
)
def test_time_range_dialog_shows_why_the_data_range_is_unavailable(monkeypatch, metadata, reason):
    app = _app_for_time_range_dialog(monkeypatch)

    options, _ = asyncio.run(_pick_time_range_option(app, None, metadata))

    data_range_options = [option for option in options if option and "Parameter data range" in str(option.prompt)]
    assert len(data_range_options) == 1
    assert data_range_options[0].disabled
    assert data_range_options[0].id is None
    assert reason in str(data_range_options[0].prompt)
    assert not [option for option in options if option and (option.id or "").startswith("data-preset-")]
    assert app.time_range == TimeRange(START, END)


def test_time_range_dialog_applies_the_last_hours_of_the_parameters_data(monkeypatch):
    app = _app_for_time_range_dialog(monkeypatch)
    metadata = {"first-sample": "2024-01-01 00:00:00", "last-sample": "2024-06-01 12:00:00"}

    options, _ = asyncio.run(_pick_time_range_option(app, "data-preset-1", metadata))

    ids = [option.id for option in options if option]
    assert ids.index("data-range") < ids.index("data-preset-0")  # listed right after the data range
    assert "Last 6 hours of data" in str(next(o for o in options if o and o.id == "data-preset-1").prompt)
    assert app.time_range == TimeRange(dt.datetime(2024, 6, 1, 6), dt.datetime(2024, 6, 1, 12))


def test_time_range_dialog_applies_a_preset_relative_to_now(monkeypatch):
    app = _app_for_time_range_dialog(monkeypatch)
    before = utc_now().replace(microsecond=0)

    options, _ = asyncio.run(_pick_time_range_option(app, "preset-1", via_key=True))  # "Last 6 hours", opened by F6

    after = utc_now()
    assert "Last 6 hours" in str(next(option for option in options if option and option.id == "preset-1").prompt)
    assert app.time_range.end - app.time_range.start == dt.timedelta(hours=6)
    assert before <= app.time_range.end <= after


def test_time_range_dialog_escape_keeps_the_range_and_remembers_nothing(monkeypatch):
    app = _app_for_time_range_dialog(monkeypatch)

    asyncio.run(_pick_time_range_option(app, None))

    assert app.time_range == TimeRange(START, END)
    assert load_recent_time_ranges() == []


def test_applied_time_ranges_are_remembered_and_offered_as_recent(monkeypatch):
    app = _app_for_time_range_dialog(monkeypatch)
    older = TimeRange(dt.datetime(2024, 3, 1), dt.datetime(2024, 3, 2))
    app.recent_time_ranges = [TimeRange(START, END), older]

    options, _ = asyncio.run(_pick_time_range_option(app, "recent-0"))

    recent_prompts = [str(option.prompt) for option in options if option and (option.id or "").startswith("recent-")]
    # the current range (START..END) is not offered again as a recent one
    assert recent_prompts == [f"{'Recent':<22}2024-03-01 00:00:00 → 2024-03-02 00:00:00"]
    assert app.time_range == older
    assert load_recent_time_ranges() == [older, TimeRange(START, END)]


def test_a_typed_time_range_is_remembered_and_used_at_the_next_startup(monkeypatch):
    app = _app_for_time_range_dialog(monkeypatch)
    new_end = dt.datetime(2025, 12, 9)

    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            while not isinstance(app.screen, _FakeMainScreen):
                await pilot.pause(0.05)
            field = app.screen.query_one("#time-range-end", Input)
            field.value = format_datetime(new_end)
            await field.action_submit()
            await pilot.pause()

    asyncio.run(run())

    assert load_recent_time_ranges() == [TimeRange(START, new_end)]
    assert must_app.MUSTApp().time_range == TimeRange(START, new_end)
