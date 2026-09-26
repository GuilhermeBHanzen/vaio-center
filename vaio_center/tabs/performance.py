"""EC performance profile and battery charge limit."""
from gi.repository import Adw, GLib, Gtk

from vaio_center.backend import wmi
from vaio_center.ui import Debouncer, Page

PRESETS = (
    ("Máxima vida útil", True, 60, 55),
    ("Equilibrado", True, 80, 75),
    ("Carga completa", False, 80, 75),
)
CUSTOM = "Personalizado"


def preset_index(enabled, stop, start):
    """Which preset the current values match; len(PRESETS) means custom."""
    for index, (_label, preset_enabled, preset_stop, preset_start) in enumerate(PRESETS):
        if not enabled and not preset_enabled:
            return index
        if enabled and preset_enabled and (stop, start) == (preset_stop, preset_start):
            return index
    return len(PRESETS)


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
        self._show_profile(app.state["profile"])
        self.combo.connect("notify::selected", self._on_profile)
        profile.add(self.combo)

        charge = self.group("Limite de carga", "Máxima vida útil (60%) é a melhor para quem fica sempre na tomada.")
        self.preset = Adw.ComboRow(
            title="Perfil de carga",
            model=Gtk.StringList.new([p[0] for p in PRESETS] + [CUSTOM]),
        )
        charge.add(self.preset)
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
        self.preset.connect("notify::selected", self._on_preset)

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
        self.preset.set_selected(preset_index(
            self.enabled.get_active(), int(self.stop.get_value()), int(self.start.get_value())))

    def _show_profile(self, code):
        self.combo.set_selected(self.codes.index(code) if code in self.codes else Gtk.INVALID_LIST_POSITION)

    def _revert_profile(self):
        with self.syncing():
            self._show_profile(self.app.state["profile"])
        return GLib.SOURCE_REMOVE

    def _on_profile(self, combo, _pspec):
        index = combo.get_selected()
        if self.is_syncing or index == Gtk.INVALID_LIST_POSITION:
            return
        code = self.codes[index]
        error = self.backend.set_profile(code)
        self.report(error)
        if error is None:
            self.app.state["profile"] = code
            self.app.save_state()
        else:
            # Failed or cancelled: show what the EC still has. Deferred because a
            # nested set_selected inside this notify handler is emitted after it returns.
            GLib.idle_add(self._revert_profile)

    def _on_preset(self, combo, _pspec):
        index = combo.get_selected()
        if self.is_syncing or index >= len(PRESETS):
            return  # "Personalizado": the user edits the values below
        _label, enabled, stop, start = PRESETS[index]
        with self.syncing():
            self.enabled.set_active(enabled)
            self.stop.set_value(stop)
            self.start.set_value(start)
        self._apply_charge()

    def _on_charge_changed(self, *_args):
        if self.is_syncing:
            return
        with self.syncing():
            self.preset.set_selected(preset_index(
                self.enabled.get_active(), int(self.stop.get_value()), int(self.start.get_value())))
        self._apply_charge()

    def _send_charge(self):
        enabled = self.enabled.get_active()
        stop = int(self.stop.get_value())
        start = int(self.start.get_value())
        if enabled and start >= stop:
            self.report("O valor de retomada precisa ser menor que o de parada.")
            return
        error = self.backend.set_charge_limit(stop, start) if enabled else self.backend.disable_charge_limit()
        self.report(error)
        if error is None:
            self.app.state["charge"] = {"enabled": enabled, "stop": stop, "start": start}
            self.app.save_state()
        else:  # failed or cancelled: show the last applied values
            with self.syncing():
                self._show_charge(self.app.state["charge"])
