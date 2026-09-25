"""GTK helpers shared by every page."""
from contextlib import contextmanager

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from vaio_center.backend.proc import CANCELLED  # noqa: E402


class Debouncer:
    """Delay a callback until calls stop arriving for delay_ms; fires with the last args."""

    def __init__(self, delay_ms, callback):
        self.delay_ms = delay_ms
        self.callback = callback
        self._source = 0
        self._args = ()

    def __call__(self, *args):
        if self._source:
            GLib.source_remove(self._source)
        self._args = args
        self._source = GLib.timeout_add(self.delay_ms, self._fire)

    def _fire(self):
        self._source = 0
        self.callback(*self._args)
        return GLib.SOURCE_REMOVE


def rgba_from_int(rgb):
    color = Gdk.RGBA()
    color.parse(f"#{rgb:06x}")
    return color


def int_from_rgba(color):
    return round(color.red * 255) << 16 | round(color.green * 255) << 8 | round(color.blue * 255)


def slider(lo, hi, step=1):
    scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, step)
    scale.set_draw_value(True)
    scale.set_size_request(260, -1)
    scale.set_valign(Gtk.Align.CENTER)
    return scale


class Page(Gtk.Box):
    key = ""
    title = ""

    def __init__(self, app):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.app = app
        self._syncing = False
        self.banner = Adw.Banner()
        self.append(self.banner)
        self.prefs = Adw.PreferencesPage(vexpand=True)
        self.append(self.prefs)

    def group(self, title, description=""):
        group = Adw.PreferencesGroup(title=title, description=description)
        self.prefs.add(group)
        return group

    def info_row(self, group, title):
        row = Adw.ActionRow(title=title, subtitle="—")
        row.add_css_class("property")
        group.add(row)
        return row

    def report(self, error):
        """Show a real error in the banner; hide it on success or a dismissed pkexec prompt."""
        failed = error is not None and error != CANCELLED
        self.banner.set_title(error if failed else "")
        self.banner.set_revealed(failed)
        return failed

    @contextmanager
    def syncing(self):
        """Wrap programmatic widget updates so change handlers can ignore them."""
        self._syncing = True
        try:
            yield
        finally:
            self._syncing = False

    @property
    def is_syncing(self):
        return self._syncing

    def refresh(self):
        """Re-read hardware state. Called on page switch and every 5 s while visible."""
