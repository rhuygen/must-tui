"""Startup with a failed login: the app goes offline and asks whether to abort or continue (ErrorDialog).

Regression tests: the startup code ran as a plain asyncio task, so its `push_screen_wait()` for that dialog raised
`NoActiveWorker` ("Task exception was never retrieved" in the log). Textual pushes the screen before that check, so
the dialog did still show, but startup never got the answer and anything after the dialog was skipped.
"""

import asyncio

import pytest

import must_tui.must_app as must_app
from must_tui.dialogs import ErrorDialog


@pytest.fixture
def failed_login(monkeypatch):
    async def fake_login(config_file=None):
        return must_app.MustContext()  # authenticated=False, as login() returns on any failure

    async def no_catalog_when_offline(*_args, **_kwargs):
        raise AssertionError("the parameter catalog must not be loaded from MUST when offline")

    monkeypatch.setattr(must_app, "login", fake_login)
    monkeypatch.setattr(must_app, "load_parameter_catalog_async", no_catalog_when_offline)

    outcome = {}
    original = must_app.MUSTApp._initialize_and_show_main_screen

    async def recording_initialize(self):
        try:
            await original(self)
        except BaseException as exc:
            outcome["error"] = exc
            raise
        outcome["completed"] = True

    monkeypatch.setattr(must_app.MUSTApp, "_initialize_and_show_main_screen", recording_initialize)
    return outcome


async def _start_until_error_dialog(app, pilot):
    for _ in range(200):  # the real startup also reads the bundled pcf.dat, give it up to 10 s
        if isinstance(app.screen, ErrorDialog):
            return app.screen
        await pilot.pause(0.05)
    raise AssertionError(f"no ErrorDialog after a failed login; screen is {app.screen!r}")


def test_a_failed_login_shows_the_abort_ignore_dialog_and_ignore_continues_offline(failed_login):
    async def main():
        app = must_app.MUSTApp()
        async with app.run_test(size=(120, 40)) as pilot:
            dialog = await _start_until_error_dialog(app, pilot)
            assert "Failed to authenticate" in str(dialog.query_one("#lbl-error-message").render())

            await pilot.click("#btn-dialog-cancel")  # "Ignore"
            await pilot.pause(0.1)

            assert isinstance(app.screen, must_app.MainScreen)
            assert app.offline_mode
            assert app.is_running
            # startup received the answer and ran to the end, instead of failing on the dialog
            assert failed_login == {"completed": True}

    asyncio.run(main())


def test_a_failed_login_then_abort_exits_the_app(failed_login):
    async def main():
        app = must_app.MUSTApp()
        async with app.run_test(size=(120, 40)) as pilot:
            await _start_until_error_dialog(app, pilot)

            await pilot.click("#btn-dialog-ok")  # "Abort"
            await pilot.pause(0.1)

            assert not app.is_running

    asyncio.run(main())
