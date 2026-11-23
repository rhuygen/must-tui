from typing import Optional, Sequence, Union
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.containers import Vertical
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button
from textual.widgets import Input
from textual.widgets import Label
from textual.widgets import Markdown
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from must_tui.time_range_input import TimeRange, format_datetime


class ErrorDialog(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "dismiss(False)", "", show=False)]

    def __init__(
        self,
        title: Optional[str] = None,
        error_message: Optional[str] = None,
        ok_label: Optional[str] = "OK",
        cancel_label: Optional[str] = "Cancel",
        quit_on_ok: bool = False,
    ) -> None:
        super().__init__()
        self._title = title or "Error"
        self._error_message = error_message or "An unexpected error has occurred."
        self._ok_label = ok_label
        self._cancel_label = cancel_label
        self._quit_on_ok = quit_on_ok

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title)
            yield Label(self._error_message, id="lbl-error-message")
            with Horizontal():
                yield Button(self._ok_label, variant="primary", id="btn-dialog-ok")
                yield Button(self._cancel_label, id="btn-dialog-cancel")

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """React to button press."""

        if event.button.id == "btn-dialog-ok":
            if self._quit_on_ok:
                self.app.exit()
            self.dismiss(True)
            # self.app.query_one("#console-log", ConsoleOutput).write_log_info("You pressed YES...")
        else:
            self.dismiss(False)
            # self.app.query_one("#console-log", ConsoleOutput).write_log_info("You pressed NO...")


class WarningDialog(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "dismiss(False)", "", show=False)]

    def __init__(
        self,
        title: Optional[str] = None,
        warning_message: Optional[str] = None,
        ok_label: Optional[str] = "OK",
    ) -> None:
        super().__init__()
        self._title = title or "Warning"
        self._warning_message = warning_message or "An unexpected warning has occurred."
        self._ok_label = ok_label

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._title)
            yield Label(self._warning_message, id="lbl-warning-message")
            with Horizontal():
                yield Button(self._ok_label, variant="primary", id="btn-dialog-ok")

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """React to button press."""

        if event.button.id == "btn-dialog-ok":
            self.dismiss(False)
            # self.app.query_one("#console-log", ConsoleOutput).write_log_info("You pressed OK...")


class HelpDialog(ModalScreen[None]):
    """Scrollable Markdown help/keyboard-shortcuts popup. Dismissed by the Close button or Escape."""

    BINDINGS = [Binding("escape", "dismiss", "", show=False)]

    def __init__(self, markdown: str) -> None:
        super().__init__()
        self._markdown = markdown

    def compose(self) -> ComposeResult:
        with Vertical():
            with VerticalScroll():
                yield Markdown(self._markdown)
            yield Button("Close", variant="primary", id="btn-dialog-close")

    @on(Button.Pressed, "#btn-dialog-close")
    def on_close_pressed(self) -> None:
        self.dismiss(None)


YAxisRangeResult = Union[tuple, str, None]
"""The dialog's result: an explicit `(ymin, ymax)`, the string `"auto"`, or `None` for cancelled."""


class YAxisRangeDialog(ModalScreen[YAxisRangeResult]):
    """Prompts for an explicit Y-axis range, or to go back to auto-scaling. Escape cancels (result `None`)."""

    BINDINGS = [Binding("escape", "dismiss(None)", "", show=False)]

    def __init__(self, default_range: Optional[tuple] = None) -> None:
        super().__init__()
        self._default_min = "" if default_range is None else str(default_range[0])
        self._default_max = "" if default_range is None else str(default_range[1])

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Y-Axis Range")
            with Horizontal():
                yield Label("Min:")
                yield Input(self._default_min, id="inp-y-min")
            with Horizontal():
                yield Label("Max:")
                yield Input(self._default_max, id="inp-y-max")
            yield Label("", id="lbl-y-range-error")
            with Horizontal():
                yield Button("Apply", variant="primary", id="btn-dialog-apply")
                yield Button("Auto", id="btn-dialog-auto")
                yield Button("Cancel", id="btn-dialog-cancel")

    @on(Button.Pressed, "#btn-dialog-apply")
    def on_apply_pressed(self) -> None:
        min_input = self.query_one("#inp-y-min", Input)
        max_input = self.query_one("#inp-y-max", Input)
        error_label = self.query_one("#lbl-y-range-error", Label)

        try:
            ymin = float(min_input.value)
            ymax = float(max_input.value)
        except ValueError:
            error_label.update("Enter a numeric value for both Min and Max.")
            return

        if not ymin < ymax:
            error_label.update("Min must be less than Max.")
            return

        self.dismiss((ymin, ymax))

    @on(Button.Pressed, "#btn-dialog-auto")
    def on_auto_pressed(self) -> None:
        self.dismiss("auto")

    @on(Button.Pressed, "#btn-dialog-cancel")
    def on_cancel_pressed(self) -> None:
        self.dismiss(None)


def format_time_range(time_range: TimeRange) -> str:
    return f"{format_datetime(time_range.start)} → {format_datetime(time_range.end)}"


class TimeRangeDialog(ModalScreen[Optional[TimeRange]]):
    """Pick a time range from presets, the selected parameter's data range, or recently used ranges.

    Selecting an entry (Enter or click) dismisses with its `TimeRange`; Escape or Cancel dismisses with `None`.
    """

    BINDINGS = [Binding("escape", "dismiss(None)", "", show=False)]

    LABEL_WIDTH = 22
    """Width of the name column in front of each range, so the ranges line up."""

    def __init__(
        self,
        current: TimeRange,
        presets: list[tuple[str, TimeRange]],
        data_range: Union[TimeRange, str],
        recent: list[TimeRange],
        data_presets: Sequence[tuple[str, TimeRange]] = (),
    ) -> None:
        """
        Args:
            current: the time range in effect now, shown for reference.
            presets: named ranges, e.g. from `time_ranges.time_range_presets()`.
            data_range: the selected parameter's data range, or why it's not available (shown, not selectable).
            recent: recently applied ranges, most recent first; `current` is left out of this list.
            data_presets: named ranges ending at the parameter's last sample, e.g. from
                `time_ranges.data_range_presets()`; shown after the data range, only when it is available.
        """

        super().__init__()
        self._current = current
        self._ranges: dict[str, TimeRange] = {}
        self._options: list[Optional[Option]] = []

        for index, (label, time_range) in enumerate(presets):
            self._add_option(f"preset-{index}", label, time_range)

        self._options.append(None)
        if isinstance(data_range, TimeRange):
            self._add_option("data-range", "Parameter data range", data_range)
            for index, (label, time_range) in enumerate(data_presets):
                self._add_option(f"data-preset-{index}", label, time_range)
        else:
            self._options.append(Option(f"{'Parameter data range':<{self.LABEL_WIDTH}}{data_range}", disabled=True))

        recent = [time_range for time_range in recent if time_range != current]
        if recent:
            self._options.append(None)
            for index, time_range in enumerate(recent):
                self._add_option(f"recent-{index}", "Recent" if index == 0 else "", time_range)

    def _add_option(self, option_id: str, label: str, time_range: TimeRange) -> None:
        self._ranges[option_id] = time_range
        self._options.append(Option(f"{label:<{self.LABEL_WIDTH}}{format_time_range(time_range)}", id=option_id))

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Time Range")
            yield Label(f"Current: {format_time_range(self._current)}", id="lbl-time-range-current")
            yield OptionList(*self._options, markup=False, id="opt-time-ranges")
            with Horizontal():
                yield Button("Cancel", id="btn-dialog-cancel")

    @on(OptionList.OptionSelected, "#opt-time-ranges")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        time_range = self._ranges.get(event.option.id or "")
        if time_range is not None:
            self.dismiss(time_range)

    @on(Button.Pressed, "#btn-dialog-cancel")
    def on_cancel_pressed(self) -> None:
        self.dismiss(None)
