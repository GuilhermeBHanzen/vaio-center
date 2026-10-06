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
BIOS_LABEL = "Definido na BIOS"


def preset_index(source, enabled, stop, start):
    """Combo position: 0 is the BIOS profile, then the presets, then custom."""
    if source == "bios":
        return 0
    for index, (_label, preset_enabled, preset_stop, preset_start) in enumerate(PRESETS):
        if not enabled and not preset_enabled:
            return 1 + index
        if enabled and preset_enabled and (stop, start) == (preset_stop, preset_start):
            return 1 + index
    return 1 + len(PRESETS)


class PerformancePage(Page):
    key = "performance"
    title = "Desempenho"

    def __init__(self, app, backend=wmi):
        super().__init__(app)
        self.backend = backend
        self.codes = list(backend.PROFILE_LABELS)
        self._charge_loaded = False
        self._ec_charge = None  # last limit read back from the firmware

        profile = self.group(
            "Perfil do firmware",
            "Muda limites de potência e a curva das ventoinhas no EC. É independente do modo do TLP.",
        )
        self.combo = Adw.ComboRow(title="Perfil", model=Gtk.StringList.new(list(backend.PROFILE_LABELS.values())))
        self._show_profile(app.state["profile"])
        self.combo.connect("notify::selected", self._on_profile)
        profile.add(self.combo)

        charge = self.group(
            "Limite de carga",
            "Definido na BIOS: o app só mostra o limite do firmware e não o altera — para mudar, use a BIOS "
            "ou escolha outro perfil. Máxima vida útil (60%) é a melhor para quem fica sempre na tomada.",
        )
        self.preset = Adw.ComboRow(
            title="Perfil de carga",
            model=Gtk.StringList.new([BIOS_LABEL] + [p[0] for p in PRESETS] + [CUSTOM]),
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
        self._ec_charge = charge
        with self.syncing():
            self._show_charge(charge)

    def _show_charge(self, charge, source=None):
        """Fill the charge rows; BIOS mode makes them a read-only view of the firmware."""
        source = source or self.app.state["charge"].get("source", "bios")
        self.enabled.set_active(charge.get("enabled", False))
        self.stop.set_value(charge.get("stop", 80))
        self.start.set_value(charge.get("start", 75))
        self.preset.set_selected(preset_index(
            source, self.enabled.get_active(), int(self.stop.get_value()), int(self.start.get_value())))
        self._set_rows_sensitive(source != "bios")

    def _set_rows_sensitive(self, sensitive):
        for row in (self.enabled, self.stop, self.start):
            row.set_sensitive(sensitive)

    def _revert_charge(self):
        """Failed or cancelled write: show what the firmware / the last applied values hold."""
        stored = self.app.state["charge"]
        bios = stored.get("source", "bios") == "bios"
        with self.syncing():
            self._show_charge(self._ec_charge if bios and self._ec_charge else stored)

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
        if self.is_syncing or index == Gtk.INVALID_LIST_POSITION:
            return
        if index == 0:  # BIOS: only display the firmware's limit, never write
            self.app.state["charge"]["source"] = "bios"
            self.app.save_state()
            with self.syncing():
                self._set_rows_sensitive(False)
            self._charge_loaded = False
            self.refresh()
            return
        self._set_rows_sensitive(True)
        if index > len(PRESETS):
            return  # "Personalizado": nothing is written until the user edits a value
        _label, enabled, stop, start = PRESETS[index - 1]
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
                "app", self.enabled.get_active(), int(self.stop.get_value()), int(self.start.get_value())))
        self._apply_charge()

    def _send_charge(self):
        if self.preset.get_selected() == 0:  # switched back to the BIOS while this write was pending
            return
        enabled = self.enabled.get_active()
        stop = int(self.stop.get_value())
        start = int(self.start.get_value())
        if enabled and start >= stop:
            self.report("O valor de retomada precisa ser menor que o de parada.")
            return
        error = self.backend.set_charge_limit(stop, start) if enabled else self.backend.disable_charge_limit()
        self.report(error)
        if error is None:
            self.app.state["charge"] = {"source": "app", "enabled": enabled, "stop": stop, "start": start}
            self.app.save_state()
        else:
            self._revert_charge()
