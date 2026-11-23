import time

import pytest


@pytest.fixture(autouse=True)
def _isolated_cache_dir(tmp_path, monkeypatch):
    """Point the cache directory to a per-test temporary one.

    The app reads and writes files there (the parameter cache, the recently used time ranges), and a test must
    neither depend on nor change the developer's real `~/.cache/must-tui/`.
    """

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))


@pytest.fixture(autouse=True)
def _local_timezone_is_not_utc(monkeypatch):
    """Run every test with a local timezone that is not UTC (Brussels: +1 h in winter, +2 h in summer).

    must-tui works in UTC throughout; on a machine (or CI runner) whose local time is UTC, a stray local-time
    conversion would go unnoticed. Unix only (`time.tzset()`); elsewhere the machine's own timezone is used.
    """

    if not hasattr(time, "tzset"):
        yield
        return
    monkeypatch.setenv("TZ", "Europe/Brussels")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()
