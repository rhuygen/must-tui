"""F8 mutes informational notifications (e.g. during a live demo); warnings and errors still show."""

import asyncio

import must_tui.must_app as must_app


def _app(monkeypatch):
    async def fake_initialize(self):
        self.install_screen(must_app.MainScreen(), name="main")
        self.push_screen("main")

    monkeypatch.setattr(must_app.MUSTApp, "_initialize_and_show_main_screen", fake_initialize)
    return must_app.MUSTApp()


def _shown(app):
    return [(notification.message, notification.severity) for notification in app._notifications]


def test_f8_mutes_informational_notifications_but_not_warnings_and_errors(monkeypatch):
    app = _app(monkeypatch)

    async def main():
        async with app.run_test(size=(160, 50)) as pilot:
            while not isinstance(app.screen, must_app.MainScreen):
                await pilot.pause(0.05)
            app.notify("before")
            await pilot.pause()
            assert _shown(app) == [("before", "information")]

            await pilot.press("f8")
            await pilot.pause()
            assert app.notifications_muted
            assert "notifications muted" in app.sub_title
            assert _shown(app) == []  # muting also clears what's on screen

            app.notify("reloading…")
            app.plot_widget.notify("from a widget")  # widgets forward to App.notify()
            app.notify("careful", severity="warning")
            app.notify("broken", severity="error")
            await pilot.pause()
            assert _shown(app) == [("careful", "warning"), ("broken", "error")]

            await pilot.press("f8")
            await pilot.pause()
            assert not app.notifications_muted
            assert "notifications muted" not in app.sub_title
            app.notify("after")
            await pilot.pause()
            assert ("after", "information") in _shown(app)

    asyncio.run(main())


def test_help_lists_the_mute_key():
    assert "| `F8` | Mute / unmute notifications" in must_app.load_help_markdown()
