"""EC performance profile and battery charge limit."""
from gi.repository import Adw, Gtk

from vaio_center.backend import wmi
from vaio_center.ui import Debouncer, Page


class PerformancePage(Page):
    key = "performance"
    title = "Desempenho"

    def __init__(self, app, backend=wmi):
        super().__init__(app)
        self.backend = backend
        self.codes = list(backend.PROFILE_LABELS)
        self._charge_loaded = False

        profile = self.group(
            "Perfil do firmware",
            "Muda limites de potência e a curva das ventoinhas no EC. É independente do modo do TLP.",
        )
        self.combo = Adw.ComboRow(title="Perfil", model=Gtk.StringList.new(list(backend.PROFILE_LABELS.values())))
        saved = app.state["profile"]
        self.combo.set_selected(self.codes.index(saved) if saved in self.codes else Gtk.INVALID_LIST_POSITION)
        self.combo.connect("notify::selected", self._on_profile)
        profile.add(self.combo)

        charge = self.group("Limite de carga", "Protege a bateria mantendo a carga entre os dois valores.")
        self.enabled = Adw.SwitchRow(title="Limitar carga")
        self.stop = Adw.SpinRow.new_with_range(50, 100, 1)
        self.stop.set_title("Parar de carregar em (%)")
        self.start = Adw.SpinRow.new_with_range(40, 99, 1)
        self.start.set_title("Voltar a carregar abaixo de (%)")
        for row in (self.enabled, self.stop, self.start):
            charge.add(row)
        with self.syncing():
            self._show_charge(app.state["charge"])
        self._apply_charge = Debouncer(400, self._send_charge)
        self.enabled.connect("notify::active", self._on_charge_changed)
        self.stop.connect("notify::value", self._on_charge_changed)
        self.start.connect("notify::value", self._on_charge_changed)

    def refresh(self):
        # Read the EC once per session; polling would spam the journal with pkexec entries.
        if self._charge_loaded:
            return
        charge = self.backend.get_charge_limit()
        error = charge.get("error")
        if error:
            self.report(error)
            self._charge_loaded = True
            return
        self._charge_loaded = True
        with self.syncing():
            self._show_charge(charge)

    def _show_charge(self, charge):
        self.enabled.set_active(charge.get("enabled", False))
        self.stop.set_value(charge.get("stop", 80))
        self.start.set_value(charge.get("start", 75))

    def _on_profile(self, combo, _pspec):
        index = combo.get_selected()
        if self.is_syncing or index == Gtk.INVALID_LIST_POSITION:
            return
        code = self.codes[index]
        if not self.report(self.backend.set_profile(code)):
            self.app.state["profile"] = code
            self.app.save_state()

    def _on_charge_changed(self, *_args):
        if not self.is_syncing:
            self._apply_charge()

    def _send_charge(self):
        enabled = self.enabled.get_active()
        stop = int(self.stop.get_value())
        start = int(self.start.get_value())
        if enabled and start >= stop:
            self.report("O valor de retomada precisa ser menor que o de parada.")
            return
        error = self.backend.set_charge_limit(stop, start) if enabled else self.backend.disable_charge_limit()
        if not self.report(error):
            self.app.state["charge"] = {"enabled": enabled, "stop": stop, "start": start}
            self.app.save_state()
