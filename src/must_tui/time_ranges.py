"""Time range presets, the startup default, and the persisted list of recently used time ranges.

The recent ranges are kept in a small JSON file next to the parameter cache:
`$XDG_CACHE_HOME/must-tui/time_ranges.json` (default `~/.cache/must-tui/time_ranges.json`). The most recent range is
first; it is also the range the app starts with. A missing, unreadable or corrupt file is not an error: the app then
starts with `default_time_range()` and an empty history.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

from textual import log

from must_tui.time_range_input import TimeRange, format_datetime, parse_datetime, utc_now

MAX_RECENT_TIME_RANGES = 10
"""How many distinct recently applied time ranges are remembered."""

DEFAULT_TIME_RANGE_DURATION = datetime.timedelta(days=1)
"""Duration of the startup time range when no range was used before: the last day, up to now."""

PRESET_DURATIONS: tuple[tuple[str, datetime.timedelta], ...] = (
    ("hour", datetime.timedelta(hours=1)),
    ("6 hours", datetime.timedelta(hours=6)),
    ("24 hours", datetime.timedelta(hours=24)),
    ("3 days", datetime.timedelta(days=3)),
    ("7 days", datetime.timedelta(days=7)),
    ("30 days", datetime.timedelta(days=30)),
)
"""Durations offered as presets, both up to now and up to a parameter's last sample."""


def get_time_range_history_path(path: str | Path | None = None) -> Path:
    """Return the JSON file used to remember recently applied time ranges."""

    if path is not None:
        return Path(path).expanduser()

    cache_root = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache")) / "must-tui"
    return cache_root / "time_ranges.json"


def default_time_range(now: datetime.datetime | None = None) -> TimeRange:
    """The range used at startup when no range was used before: the last day, up to now (UTC, to the second)."""

    now = (now or utc_now()).replace(microsecond=0)
    return TimeRange(now - DEFAULT_TIME_RANGE_DURATION, now)


def time_range_presets(now: datetime.datetime | None = None) -> list[tuple[str, TimeRange]]:
    """Named time ranges relative to `now`: the last hour/6 h/24 h/3 d/7 d/30 d, today (so far) and yesterday.

    `now` defaults to the current UTC time. Today runs from UTC midnight to now, yesterday from the previous
    midnight to midnight. A preset that would not
    be a valid range (only "Today", exactly at midnight) is left out.
    """

    now = (now or utc_now()).replace(microsecond=0)
    midnight = now.replace(hour=0, minute=0, second=0)

    presets = [(f"Last {name}", TimeRange(now - duration, now)) for name, duration in PRESET_DURATIONS]
    presets.append(("Today", TimeRange(midnight, now)))
    presets.append(("Yesterday", TimeRange(midnight - datetime.timedelta(days=1), midnight)))
    return [(label, time_range) for label, time_range in presets if time_range.is_valid()]


def data_range_presets(data_range: TimeRange) -> list[tuple[str, TimeRange]]:
    """The last hour/6 h/24 h/3 d/7 d/30 d of a parameter's data: ranges ending at its last sample.

    The start is not clamped to the first sample: when the parameter has less data than the duration, the range
    simply starts before it, so the plot shows that the data starts later.
    """

    end = data_range.end
    return [(f"Last {name} of data", TimeRange(end - duration, end)) for name, duration in PRESET_DURATIONS]


def add_recent_time_range(recent: list[TimeRange], time_range: TimeRange) -> list[TimeRange]:
    """Return `recent` with `time_range` moved (or added) to the front, without duplicates, capped in length."""

    return [time_range, *(item for item in recent if item != time_range)][:MAX_RECENT_TIME_RANGES]


def load_recent_time_ranges(path: str | Path | None = None) -> list[TimeRange]:
    """Read the remembered time ranges, most recent first. Returns `[]` when there are none or the file is unusable.

    Entries that can't be parsed or aren't a valid range (start before end) are skipped.
    """

    history_path = get_time_range_history_path(path)
    try:
        content = json.loads(history_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        log.warning(f"Could not read the recent time ranges from {history_path}: {exc}")
        return []

    entries = content.get("recent", []) if isinstance(content, dict) else []
    if not isinstance(entries, list):
        return []

    recent: list[TimeRange] = []
    for entry in entries:
        try:
            time_range = TimeRange(parse_datetime(entry["start"]), parse_datetime(entry["end"]))
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if time_range.is_valid() and time_range not in recent:
            recent.append(time_range)
    return recent[:MAX_RECENT_TIME_RANGES]


def save_recent_time_ranges(recent: list[TimeRange], path: str | Path | None = None) -> bool:
    """Write the remembered time ranges, most recent first. Returns `False` (and logs why) when that failed.

    The file is written to a temporary name first and then renamed, so a crash halfway can't leave it truncated.
    """

    history_path = get_time_range_history_path(path)
    content = {
        "recent": [
            {"start": format_datetime(item.start), "end": format_datetime(item.end)}
            for item in recent[:MAX_RECENT_TIME_RANGES]
        ]
    }
    tmp_path = history_path.with_name(history_path.name + ".tmp")
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
        tmp_path.replace(history_path)
    except OSError as exc:
        log.warning(f"Could not save the recent time ranges to {history_path}: {exc}")
        return False
    return True
