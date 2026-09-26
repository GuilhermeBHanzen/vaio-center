"""GTK application: owns the saved state and the refresh tick. Fan control lives in the daemon."""
import signal

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib  # noqa: E402

try:
    gi.require_version("GLibUnix", "2.0")
    from gi.repository import GLibUnix  # noqa: E402

    unix_signal_add = GLibUnix.signal_add
except (ImportError, ValueError):
    unix_signal_add = GLib.unix_signal_add

from vaio_center.backend import state as state_store  # noqa: E402
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
        self.window = None
        self.pages = {}

    def save_state(self):
        state_store.save(self.state)

    def do_activate(self):
        if self.window is None:
            self.pages = {cls.key: cls(self) for cls in PAGES}
            self.window = MainWindow(self, list(self.pages.values()))
            for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                unix_signal_add(GLib.PRIORITY_DEFAULT, signum, self._on_signal)
            GLib.timeout_add(REFRESH_MS, self._tick)
        self.window.present()
        self.window.refresh_visible()

    def _tick(self):
        self.window.refresh_visible()
        return GLib.SOURCE_CONTINUE

    def _on_signal(self):
        self.quit()
        return GLib.SOURCE_REMOVE
