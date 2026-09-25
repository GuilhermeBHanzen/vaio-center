"""TLP mode page: same modes and state file as the waybar TLP module."""
from gi.repository import Adw, Gtk

from vaio_center.backend import tlp
from vaio_center.ui import Page

LABELS = {"performance": "Desempenho", "balanced": "Equilibrado", "power-saver": "Economia"}


class PowerPage(Page):
    key = "power"
    title = "Energia (TLP)"

    def __init__(self, app, backend=tlp):
        super().__init__(app)
        self.backend = backend
        group = self.group("Modo do TLP", "O mesmo modo do módulo TLP da waybar. Pede a senha de administrador.")
        self.checks = {}
        leader = None
        for mode in backend.MODES:
            check = Gtk.CheckButton()
            if leader is None:
                leader = check
            else:
                check.set_group(leader)
            check.connect("toggled", self._on_toggled, mode)
            row = Adw.ActionRow(title=LABELS[mode])
            row.add_prefix(check)
            row.set_activatable_widget(check)
            group.add(row)
            self.checks[mode] = check

    def refresh(self):
        mode = self.backend.get_mode()
        with self.syncing():
            if mode in self.checks:
                self.checks[mode].set_active(True)

    def _on_toggled(self, check, mode):
        if self.is_syncing or not check.get_active():
            return
        error = self.backend.set_mode(mode)
        self.report(error)
        if error is not None:
            self.refresh()
