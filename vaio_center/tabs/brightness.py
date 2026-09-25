"""Screen brightness page."""
from gi.repository import Adw

from vaio_center.backend import brightness
from vaio_center.ui import Debouncer, Page, slider


class BrightnessPage(Page):
    key = "brightness"
    title = "Tela"

    def __init__(self, app, backend=brightness):
        super().__init__(app)
        self.backend = backend
        group = self.group("Brilho da tela")
        self.scale = slider(1, 100)
        self._apply = Debouncer(150, self._send)
        self.scale.connect("value-changed", self._on_changed)
        row = Adw.ActionRow(title="Brilho (%)")
        row.add_suffix(self.scale)
        group.add(row)

    def refresh(self):
        percent = self.backend.get_percent()
        if percent is None:
            self.report("Não foi possível ler o brilho (brightnessctl).")
            return
        with self.syncing():
            self.scale.set_value(percent)

    def _on_changed(self, scale):
        if not self.is_syncing:
            self._apply(int(scale.get_value()))

    def _send(self, percent):
        self.report(self.backend.set_percent(percent))
