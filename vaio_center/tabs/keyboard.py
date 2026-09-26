"""Keyboard backlight page: one color (the keyboard is single-zone) and brightness."""
from gi.repository import Adw, Gtk

from vaio_center.backend import kbdlevel, wmi
from vaio_center.ui import Debouncer, Page, int_from_rgba, rgba_from_int, slider


def _percent(level):
    return round(level * 100 / 255)


class KeyboardPage(Page):
    key = "keyboard"
    title = "Teclado"

    def __init__(self, app, backend=wmi, levels=kbdlevel):
        super().__init__(app)
        self.backend = backend
        self.levels = levels

        colors = self.group("Cor", "O teclado tem uma zona só: a cor vale para o teclado todo.")
        dialog = Gtk.ColorDialog()
        dialog.set_with_alpha(False)
        self.color = Gtk.ColorDialogButton(dialog=dialog, valign=Gtk.Align.CENTER)
        self.color.set_rgba(rgba_from_int(app.state["keyboard"]["color"]))
        self.color.connect("notify::rgba", self._on_color)
        row = Adw.ActionRow(title="Cor do teclado")
        row.add_suffix(self.color)
        colors.add(row)

        light = self.group("Brilho do teclado", "As teclas de brilho do teclado também mudam este valor.")
        self.level = slider(0, 100)
        with self.syncing():
            self.level.set_value(_percent(levels.load()))
        self._apply_level = Debouncer(150, self._send_level)
        self.level.connect("value-changed", self._on_level)
        row = Adw.ActionRow(title="Brilho (%)")
        row.add_suffix(self.level)
        light.add(row)

    def refresh(self):
        # The daemon changes the level when the Fn keys are pressed; follow it.
        with self.syncing():
            self.level.set_value(_percent(self.levels.load()))

    def _on_color(self, button, _pspec):
        rgb = int_from_rgba(button.get_rgba())
        error = self.backend.set_keyboard_color(rgb)
        self.report(error)
        if error is None:
            self.app.state["keyboard"]["color"] = rgb
            self.app.save_state()

    def _on_level(self, scale):
        if not self.is_syncing:
            self._apply_level(int(scale.get_value()))

    def _send_level(self, percent):
        level = self.backend.byte_from_percent(percent)
        error = self.backend.set_keyboard_brightness(level)
        self.report(error)
        if error is None:
            self.levels.save(level)
