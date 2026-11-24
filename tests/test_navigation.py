"""Pan/zoom of the time range from the plot: keys and mouse wheel, debounced commit, and fetching only when needed."""

import asyncio
import datetime as dt
import json
import re

import plotext

import pytest
from textual.widgets import Input

import must_tui.must_app as must_app
from must_tui.must_app import ParameterMetadata, TimeRangePlotter, format_binding_key, load_help_markdown
from must_tui.time_range_input import TimeRange, format_datetime
from must_tui.time_ranges import load_recent_time_ranges, pan_time_range, zoom_time_range

START = dt.datetime(2025, 12, 2)
END = dt.datetime(2025, 12, 3)
DAY = TimeRange(START, END)


# --- pure helpers


@pytest.mark.parametrize(
    "fraction, expected",
    [
        (0.5, TimeRange(dt.datetime(2025, 12, 2, 12), dt.datetime(2025, 12, 3, 12))),
        (-0.5, TimeRange(dt.datetime(2025, 12, 1, 12), dt.datetime(2025, 12, 2, 12))),
    ],
)
def test_pan_time_range(fraction, expected):
    assert pan_time_range(DAY, fraction) == expected


def test_pan_moves_at_least_one_second():
    one_second = TimeRange(START, START + dt.timedelta(seconds=1))

    assert pan_time_range(one_second, 0.5) == TimeRange(START + dt.timedelta(seconds=1), START + dt.timedelta(seconds=2))
    assert pan_time_range(one_second, -0.5) == TimeRange(START - dt.timedelta(seconds=1), START)


def test_pan_beyond_the_supported_years_is_refused():
    assert pan_time_range(TimeRange(dt.datetime(9999, 12, 31), dt.datetime(9999, 12, 31, 12)), 1) is None
    assert pan_time_range(TimeRange(dt.datetime(1000, 1, 1), dt.datetime(1000, 1, 1, 12)), -1) is None


def test_zoom_time_range_around_the_centre():
    assert zoom_time_range(DAY, 0.5) == TimeRange(dt.datetime(2025, 12, 2, 6), dt.datetime(2025, 12, 2, 18))
    assert zoom_time_range(DAY, 2) == TimeRange(dt.datetime(2025, 12, 1, 12), dt.datetime(2025, 12, 3, 12))


def test_zoom_keeps_whole_seconds_and_at_least_one_second():
    three_seconds = TimeRange(START, START + dt.timedelta(seconds=3))

    zoomed = zoom_time_range(three_seconds, 0.5)  # 1.5 s rounds to 2 s, start on a whole second

    assert zoomed is not None
    assert zoomed.end - zoomed.start == dt.timedelta(seconds=2)
    assert zoomed.start.microsecond == 0
    assert zoom_time_range(TimeRange(START, START + dt.timedelta(seconds=1)), 0.5) is None  # can't get shorter


def test_zoom_out_beyond_the_supported_years_is_refused():
    assert zoom_time_range(TimeRange(dt.datetime(9999, 6, 1), dt.datetime(9999, 12, 1)), 4) is None


@pytest.mark.parametrize(
    "key, expected",
    [("plus,equals_sign", "+ / ="), ("minus", "-"), ("left", "←"), ("0", "0"), ("ctrl+q", "Ctrl+Q")],
)
def test_format_binding_key_for_plot_keys(key, expected):
    assert format_binding_key(key) == expected


def test_help_lists_the_plot_keys():
    help_text = load_help_markdown()

    assert "<!-- PLOT_KEYBINDINGS -->" not in help_text
    for binding in TimeRangePlotter.BINDINGS:
        assert f"| `{format_binding_key(binding.key)}` | {binding.description} |" in help_text


# --- the plot widget


def _hours(*hours):
    return [START + dt.timedelta(hours=hour) for hour in hours]


def test_covers_needs_every_series_fetched_completely_for_a_containing_range():
    plotter = TimeRangePlotter(must_app.MustContext())
    asyncio.run(plotter.update("A", _hours(1, 2), [1.0, 2.0], DAY))

    assert plotter.covers(TimeRange(START + dt.timedelta(hours=6), START + dt.timedelta(hours=12)))
    assert plotter.covers(DAY)
    assert not plotter.covers(TimeRange(START, END + dt.timedelta(seconds=1)))

    asyncio.run(plotter.update("B", _hours(1), [1.0], DAY, truncated=True))
    assert not plotter.covers(TimeRange(START + dt.timedelta(hours=6), START + dt.timedelta(hours=12)))

    plotter.clear_plot()
    assert plotter.covers(DAY)  # nothing plotted: nothing to fetch


def test_series_are_drawn_from_full_resolution_data_within_the_limits():
    plotter = TimeRangePlotter(must_app.MustContext())
    timestamps = [START + dt.timedelta(seconds=10 * i) for i in range(8640)]  # a day, every 10 s
    values = [float(i) for i in range(8640)]
    plotter.set_xlimits(START, END)
    asyncio.run(plotter.update("A", timestamps, values, DAY))
    assert len(plotter.display_series[0][0]) <= must_app.MAX_PLOT_POINTS

    plotter.set_xlimits(START, START + dt.timedelta(minutes=30))  # 181 samples: all of them, not downsampled
    plotter.refresh_detail()

    # ... plus the next sample just outside the limits (there is none before START), for the line towards it
    assert plotter.display_series[0][1] == values[:182]


def test_unsorted_samples_are_sorted_by_time():
    plotter = TimeRangePlotter(must_app.MustContext())
    asyncio.run(plotter.update("A", _hours(3, 1, 2), [3.0, 1.0, 2.0], DAY))

    assert plotter.time == [_hours(1, 2, 3)]
    assert plotter.data == [[1.0, 2.0, 3.0]]


# --- the app


def _ms(moment):
    return int(moment.replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


@pytest.fixture
def nav_app(monkeypatch):
    """The real MainScreen, with a fake MUST that returns a sample per minute and records each fetch."""

    fetches = []
    truncate = {"enabled": False, "gate": None}

    async def fake_initialize(self):
        self.install_screen(must_app.MainScreen(), name="main")
        self.push_screen("main")

    async def fake_get_parameter_data(_ctx, _provider, name, start, end, paginated=False, truncated=None):
        fetches.append((name, start, end))
        if truncate["gate"] is not None:
            await truncate["gate"].wait()
        first, last = dt.datetime.fromisoformat(start), dt.datetime.fromisoformat(end)
        minutes = int((last - first).total_seconds() // 60)
        data = [{"date": str(_ms(first + dt.timedelta(minutes=m))), "value": float(m)} for m in range(minutes + 1)]
        if truncate["enabled"] and truncated is not None:
            truncated.append(True)
        yield {"content": [{"data": data}]}

    monkeypatch.setattr(must_app.MUSTApp, "_initialize_and_show_main_screen", fake_initialize)
    monkeypatch.setattr(must_app, "get_parameter_data", fake_get_parameter_data)
    app = must_app.MUSTApp()
    app.time_range = DAY
    return app, fetches, truncate


async def _plotted(app, pilot, name="PAR_A"):
    while not isinstance(app.screen, must_app.MainScreen):
        await pilot.pause(0.05)
    await pilot.pause()
    await app.plot_parameter(name).wait()
    await pilot.pause()
    await pilot.click(TimeRangePlotter)  # focuses the plot
    await pilot.pause()
    assert app.focused is app.plot_widget


async def _settle(app, pilot):
    """Wait for the debounced commit and any reload it started."""

    await pilot.pause(must_app.NAVIGATION_DEBOUNCE + 0.2)
    for worker in list(app.workers):
        if worker.group in ("navigate", "reload"):
            await worker.wait()
    await pilot.pause()


def test_a_burst_of_pans_shows_at_once_and_fetches_once(nav_app):
    app, fetches, _ = nav_app

    async def main():
        async with app.run_test(size=(160, 50)) as pilot:
            await _plotted(app, pilot)
            assert len(fetches) == 1

            for _ in range(5):
                await pilot.press("right")
            expected = TimeRange(START + dt.timedelta(days=2.5), END + dt.timedelta(days=2.5))
            # immediately: the fields and the TUI x-axis follow each key
            assert app.time_range == expected
            assert app.screen.query_one("#time-range-start", Input).value == format_datetime(expected.start)
            assert app.plot_widget.xlimits == (expected.start, expected.end)

            await _settle(app, pilot)
            assert fetches[1:] == [("PAR_A", format_datetime(expected.start), format_datetime(expected.end))]
            assert app.plot_widget.fetched_ranges == [(expected, False)]

    asyncio.run(main())


def test_zooming_in_within_the_loaded_data_does_not_fetch_and_shows_detail(nav_app):
    app, fetches, _ = nav_app

    async def main():
        async with app.run_test(size=(160, 50)) as pilot:
            await _plotted(app, pilot)
            for _ in range(3):
                await pilot.press("plus")  # 24 h -> 3 h
            await _settle(app, pilot)

            assert len(fetches) == 1
            assert app.time_range == TimeRange(dt.datetime(2025, 12, 2, 10, 30), dt.datetime(2025, 12, 2, 13, 30))
            # all 181 samples of those 3 hours, not what was left of them after downsampling 1441 to 1000, plus
            # the nearest sample on either side for the lines to them
            assert len(app.plot_widget.display_series[0][0]) == 183

            await pilot.press("minus")  # zooming back out within the loaded day doesn't fetch either
            await _settle(app, pilot)
            assert len(fetches) == 1

    asyncio.run(main())


def test_zooming_in_on_truncated_data_fetches_again(nav_app):
    app, fetches, truncate = nav_app
    truncate["enabled"] = True

    async def main():
        async with app.run_test(size=(160, 50)) as pilot:
            await _plotted(app, pilot)
            await pilot.press("equals_sign")
            await _settle(app, pilot)

            assert len(fetches) == 2

    asyncio.run(main())


def test_the_mouse_wheel_zooms_in_smaller_steps(nav_app):
    app, fetches, _ = nav_app

    class _WheelEvent:
        def stop(self):
            pass

    async def main():
        async with app.run_test(size=(160, 50)) as pilot:
            await _plotted(app, pilot)
            app.plot_widget.zoom_in(_WheelEvent())  # the MouseScrollUp handler
            await pilot.pause()
            assert app.time_range.end - app.time_range.start == dt.timedelta(hours=24 / must_app.WHEEL_ZOOM_FACTOR)

            app.plot_widget.zoom_out(_WheelEvent())  # the MouseScrollDown handler
            await pilot.pause()
            assert app.time_range == DAY

    asyncio.run(main())


def test_a_reload_finishing_after_a_newer_view_keeps_the_newer_view(nav_app):
    app, fetches, truncate = nav_app

    async def main():
        async with app.run_test(size=(160, 50)) as pilot:
            await _plotted(app, pilot)
            truncate["gate"] = gate = asyncio.Event()  # from now on, fetches wait until released

            await pilot.press("right")  # not covered: a reload for the panned range starts after the debounce
            await pilot.pause(must_app.NAVIGATION_DEBOUNCE + 0.2)
            assert len(fetches) == 2  # the reload is waiting in its fetch
            await pilot.press("left")  # back within the loaded day: covered, so no fetch for this one
            await pilot.pause(must_app.NAVIGATION_DEBOUNCE + 0.2)
            gate.set()
            await _settle(app, pilot)

            assert app.time_range == DAY
            assert app.plot_widget.xlimits == (START, END)
            assert len(fetches) == 2

    asyncio.run(main())


def test_reset_goes_to_the_parameters_data_range_or_explains_why_not(nav_app):
    app, fetches, _ = nav_app

    async def main():
        async with app.run_test(size=(160, 50)) as pilot:
            await _plotted(app, pilot)
            notes = []
            app.notify = lambda message, **kwargs: notes.append(message)

            await pilot.press("0")
            await pilot.pause()
            assert app.time_range == DAY
            assert notes and "Select a parameter" in notes[0]

            await app.screen.query_one(ParameterMetadata).update_metadata(
                "PAR_A", {"first-sample": "2025-12-01 06:00:00", "last-sample": "2025-12-02 18:00:00"}
            )
            await pilot.press("0")
            await pilot.pause()
            assert app.time_range == TimeRange(dt.datetime(2025, 12, 1, 6), dt.datetime(2025, 12, 2, 18))

    asyncio.run(main())


def test_exploring_by_pan_and_zoom_remembers_only_the_last_view(nav_app):
    app, fetches, _ = nav_app

    async def main():
        async with app.run_test(size=(160, 50)) as pilot:
            await _plotted(app, pilot)
            app._remember_time_range(DAY)  # e.g. typed before
            await pilot.press("right")
            await _settle(app, pilot)
            await pilot.press("plus")
            await _settle(app, pilot)

            assert load_recent_time_ranges() == [app.time_range, DAY]

    asyncio.run(main())


# --- lines across the edges, and points only (F7)


def _gap_series():
    """Samples at 0 up to 06:00, none until 18:00, then at 10: a gap that a line plot bridges with a ramp."""

    timestamps = _hours(0, 3, 6, 18, 21, 24)
    return timestamps, [0.0, 0.0, 0.0, 10.0, 10.0, 10.0]


def test_zooming_in_keeps_the_line_across_a_gap_at_the_edge():
    # Regression test: zooming in to a range that starts inside a gap (without fetching again) dropped the sample
    # before the limits, and with it the line bridging the gap into view.
    plotter = TimeRangePlotter(must_app.MustContext())
    plotter.set_xlimits(START, END)
    asyncio.run(plotter.update("A", *_gap_series(), DAY))

    plotter.set_xlimits(START + dt.timedelta(hours=9), END)
    plotter.refresh_detail()
    times, values = plotter.display_series[0]

    assert values == [0.0, 10.0, 10.0, 10.0]  # the 06:00 sample before the limits is kept
    assert times[0] == must_app.utc_timestamp(START + dt.timedelta(hours=6))
    # and the line is drawn into view: the canvas's first column has a point, below the top (10) row
    rendered = plotext.uncolorize(plotter.plt.build())
    canvas = [re.sub(r"^[^┤│]*[┤│]", "", row.rstrip())[:-1] for row in rendered.splitlines() if row.rstrip().endswith("│")]
    first_column = [row[:1] for row in canvas]
    assert "•" in first_column[1:]


def test_points_only_draws_no_lines():
    plotter = TimeRangePlotter(must_app.MustContext())
    plotter.set_xlimits(START, END)
    asyncio.run(plotter.update("A", *_gap_series(), DAY))
    with_lines = plotext.uncolorize(plotter.plt.build()).count("•")

    plotter.points_only = True
    points = plotext.uncolorize(plotter.plt.build()).count("•")

    assert points == 6  # one per sample, nothing between them
    assert with_lines > points


def test_f7_toggles_points_only_for_both_backends(nav_app):
    app, _, _ = nav_app

    async def main():
        async with app.run_test(size=(160, 50)) as pilot:
            await _plotted(app, pilot)
            await pilot.press("f7")
            await pilot.pause()
            assert app.points_only and app.plot_widget.points_only and app.matplotlib_plotter.points_only
            assert "points only" in app.sub_title

            await pilot.press("f7")
            await pilot.pause()
            assert not (app.points_only or app.plot_widget.points_only or app.matplotlib_plotter.points_only)

    asyncio.run(main())


def test_matplotlib_gets_points_only_in_its_state():
    sent = []

    class _Pipe:
        def write(self, text):
            sent.append(json.loads(text))

        def flush(self):
            pass

    plotter = must_app.MatplotlibPlotter()
    plotter._stdin = _Pipe()
    tui = TimeRangePlotter(must_app.MustContext())
    tui.points_only = True

    plotter.sync_from_plotter(tui)

    assert sent[-1]["points_only"] is True


def test_ctrl_takes_quarter_steps(nav_app):
    app, _, _ = nav_app
    hour = dt.timedelta(hours=1)

    async def main():
        async with app.run_test(size=(160, 50)) as pilot:
            await _plotted(app, pilot)

            await pilot.press("ctrl+right")  # a quarter of the 24 h range
            assert app.time_range == TimeRange(START + 6 * hour, END + 6 * hour)
            await pilot.press("ctrl+left")
            assert app.time_range == DAY

            await pilot.press("ctrl+up")  # zoom in by a quarter: 24 h -> 18 h, around the same centre
            assert app.time_range == TimeRange(START + 3 * hour, END - 3 * hour)
            await pilot.press("ctrl+down")  # and back out
            assert app.time_range == DAY

            for key in ("shift+left", "shift+right", "shift+up", "shift+down"):  # left to tmux
                await pilot.press(key)
            assert app.time_range == DAY

    asyncio.run(main())


def test_the_plot_shows_a_border_when_focused_like_the_option_list(nav_app):
    app, _, _ = nav_app

    async def main():
        async with app.run_test(size=(160, 50)) as pilot:
            while not isinstance(app.screen, must_app.MainScreen):
                await pilot.pause(0.05)
            await pilot.pause()
            option_list = app.screen.query_one("OptionList")

            option_list.focus()
            await pilot.pause()
            focused_list, blurred_plot = option_list.styles.border_top, app.plot_widget.styles.border_top

            app.plot_widget.focus()
            await pilot.pause()
            blurred_list, focused_plot = option_list.styles.border_top, app.plot_widget.styles.border_top

            assert focused_plot == focused_list and focused_plot[0] == "tall"
            assert blurred_plot == blurred_list
            assert focused_plot != blurred_plot

    asyncio.run(main())


def test_one_quick_zoom_gives_one_notification(nav_app):
    app, fetches, _ = nav_app
    messages = []
    app.notify = lambda message, **kwargs: messages.append(message)

    async def main():
        async with app.run_test(size=(160, 50)) as pilot:
            await _plotted(app, pilot)
            messages.clear()

            await pilot.press("minus")
            await _settle(app, pilot)

            assert len(fetches) == 2
            assert len(messages) == 1 and messages[0].startswith("Reloaded 1 of 1 parameter(s)")

    asyncio.run(main())
