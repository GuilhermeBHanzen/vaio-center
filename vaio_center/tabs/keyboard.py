"""Keyboard backlight page: 3 RGB zones, brightness and per-zone calibration."""
from gi.repository import Adw, Gtk

from vaio_center.backend import wmi
from vaio_center.ui import Debouncer, Page, int_from_rgba, rgba_from_int, slider

ZONES = ("Esquerda", "Meio", "Direita")


class KeyboardPage(Page):
    key = "keyboard"
    title = "Teclado"

    def __init__(self, app, backend=wmi):
        super().__init__(app)
        self.backend = backend
        keyboard = app.state["keyboard"]

        colors = self.group("Cor por zona")
        self.buttons = []
        for zone, name in enumerate(ZONES):
            button = self._color_button(keyboard["zones"][zone])
            button.connect("notify::rgba", self._on_zone_color, zone)
            self._add_row(colors, name, button)
            self.buttons.append(button)
        self.all_button = self._color_button(keyboard["zones"][0])
        self.all_button.connect("notify::rgba", self._on_all_color)
        self._add_row(colors, "Todas as zonas", self.all_button)

        light = self.group("Brilho do teclado")
        self.level = slider(0, 100)
        self.level.set_value(round(keyboard["brightness"] * 100 / 255))
        self._apply_level = Debouncer(150, self._send_level)
        self.level.connect("value-changed", lambda scale: self._apply_level(int(scale.get_value())))
        self._add_row(light, "Brilho (%)", self.level)

        calibration = self.group(
            "Calibração",
            "A mesma cor pode sair mais forte numa zona (neste teclado, a direita). "
            "Reduza a zona mais forte até as três parecerem iguais.",
        )
        self._apply_calibration = Debouncer(200, self._send_all_zones)
        for zone, name in enumerate(ZONES):
            spin = Adw.SpinRow.new_with_range(50, 100, 1)
            spin.set_title(f"{name} (%)")
            spin.set_value(keyboard["calibration"][zone])
            spin.connect("notify::value", self._on_calibration, zone)
            calibration.add(spin)

    @staticmethod
    def _color_button(rgb):
        dialog = Gtk.ColorDialog()
        dialog.set_with_alpha(False)
        button = Gtk.ColorDialogButton(dialog=dialog, valign=Gtk.Align.CENTER)
        button.set_rgba(rgba_from_int(rgb))
        return button

    @staticmethod
    def _add_row(group, title, widget):
        row = Adw.ActionRow(title=title)
        row.add_suffix(widget)
        group.add(row)

    def _send_zone(self, zone):
        keyboard = self.app.state["keyboard"]
        return self.backend.set_zone_color(zone, keyboard["zones"][zone], keyboard["calibration"][zone])

    def _on_zone_color(self, button, _pspec, zone):
        self.app.state["keyboard"]["zones"][zone] = int_from_rgba(button.get_rgba())
        if not self.report(self._send_zone(zone)):
            self.app.save_state()

    def _on_all_color(self, button, _pspec):
        # Each zone button's notify::rgba handler sends its own (calibrated) color.
        for zone_button in self.buttons:
            zone_button.set_rgba(button.get_rgba())

    def _on_calibration(self, spin, _pspec, zone):
        self.app.state["keyboard"]["calibration"][zone] = int(spin.get_value())
        self._apply_calibration()

    def _send_all_zones(self):
        errors = [error for error in (self._send_zone(zone) for zone in range(len(ZONES))) if error]
        if not self.report(errors[0] if errors else None):
            self.app.save_state()

    def _send_level(self, percent):
        level = self.backend.byte_from_percent(percent)
        self.app.state["keyboard"]["brightness"] = level
        if not self.report(self.backend.set_keyboard_brightness(level)):
            self.app.save_state()
