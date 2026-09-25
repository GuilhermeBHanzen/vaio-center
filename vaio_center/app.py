"""GTK application: owns the saved state, the fan guard and the refresh tick."""
import signal

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib  # noqa: E402

from vaio_center.backend import state as state_store  # noqa: E402
from vaio_center.fan_guard import FanGuard  # noqa: E402
from vaio_center.window import MainWindow  # noqa: E402
from vaio_center.tabs.battery import BatteryPage  # noqa: E402
from vaio_center.tabs.power import PowerPage  # noqa: E402
from vaio_center.tabs.brightness import BrightnessPage  # noqa: E402
from vaio_center.tabs.gpu import GpuPage  # noqa: E402
from vaio_center.tabs.keyboard import KeyboardPage  # noqa: E402
from vaio_center.tabs.fans import FansPage  # noqa: E402
from vaio_center.tabs.performance import PerformancePage  # noqa: E402

APP_ID = "org.local.VaioCenter"
REFRESH_MS = 5000

# Page classes in sidebar order. Each is constructed with the app as its only argument.
PAGES = [PerformancePage, FansPage, KeyboardPage, BatteryPage, PowerPage, BrightnessPage, GpuPage]


class VaioCenter(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.state = state_store.load()
        self.guard = FanGuard()
        self.window = None
        self.pages = {}
        # Runs on every way out: last window closed, SIGINT/SIGTERM, logout.
        self.connect("shutdown", lambda _app: self.guard.release())

    def save_state(self):
        state_store.save(self.state)

    def do_activate(self):
        if self.window is None:
            self.pages = {cls.key: cls(self) for cls in PAGES}
            self.window = MainWindow(self, list(self.pages.values()))
            self._watch_sleep()
            for signum in (signal.SIGINT, signal.SIGTERM):
                GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, self._on_signal)
            GLib.timeout_add(REFRESH_MS, self._tick)
        self.window.present()
        self.window.refresh_visible()

    def _tick(self):
        if self.guard.check() and "fans" in self.pages:
            self.pages["fans"].on_forced_auto()
        self.window.refresh_visible()
        return GLib.SOURCE_CONTINUE

    def _watch_sleep(self):
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        except GLib.Error:
            return
        bus.signal_subscribe(
            "org.freedesktop.login1",
            "org.freedesktop.login1.Manager",
            "PrepareForSleep",
            "/org/freedesktop/login1",
            None,
            Gio.DBusSignalFlags.NONE,
            self._on_sleep,
        )

    def _on_sleep(self, *_args):
        # Fires before suspend (True) and after resume (False). The pre-suspend call
        # may not finish in time; the post-resume one always does.
        self.guard.release()

    def _on_signal(self):
        self.quit()
        return GLib.SOURCE_REMOVE
