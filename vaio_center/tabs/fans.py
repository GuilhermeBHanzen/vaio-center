"""Fan page: live readings plus Automático / Manual / Máximo."""
from gi.repository import Adw, Gtk

from vaio_center.backend import sensors, wmi
from vaio_center.fan_guard import LIMIT_C, MIN_PCT
from vaio_center.ui import Debouncer, Page, slider

MODES = (
    ("auto", "Automático", "O firmware controla as ventoinhas."),
    ("manual", "Manual", "Velocidade fixa, definida abaixo."),
    ("max", "Máximo", "As duas ventoinhas a 100%, igual ao Fn+1."),
)


def _fmt_rpm(value):
    return "parada" if value == 0 else f"{value} RPM"


class FansPage(Page):
    key = "fans"
    title = "Ventoinhas"

    def __init__(self, app, backend=wmi, temps=sensors):
        super().__init__(app)
        self.backend = backend
        self.temps = temps
        self.guard = app.guard

        live = self.group("Leitura")
        self.fan1 = self.info_row(live, "Ventoinha 1")
        self.fan2 = self.info_row(live, "Ventoinha 2")
        self.duty = self.info_row(live, "Potência da ventoinha 1")
        self.cpu = self.info_row(live, "Temperatura da CPU")

        control = self.group(
            "Controle",
            f"Manual e Máximo voltam sozinhos para Automático ao fechar o app, "
            f"ao suspender ou se a CPU chegar a {LIMIT_C} °C.",
        )
        self.checks = {}
        leader = None
        for mode, label, subtitle in MODES:
            check = Gtk.CheckButton()
            if leader is None:
                leader = check
            else:
                check.set_group(leader)
            check.connect("toggled", self._on_mode, mode)
            row = Adw.ActionRow(title=label, subtitle=subtitle)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            control.add(row)
            self.checks[mode] = check

        self.speed = slider(MIN_PCT, 100)
        self.speed.set_value(app.state["fan"]["duty_pct"])
        self._apply_speed = Debouncer(300, self._send_manual)
        self.speed.connect("value-changed", self._on_speed)
        row = Adw.ActionRow(title="Velocidade manual (%)")
        row.add_suffix(self.speed)
        control.add(row)
        self._sync_mode()

    def refresh(self):
        cpu = self.temps.cpu_temp_c()
        self.cpu.set_subtitle("—" if cpu is None else f"{cpu:.0f} °C")
        fans = self.backend.read_fans()
        if "error" in fans:
            self.report(fans["error"])
            return
        self.fan1.set_subtitle(_fmt_rpm(fans["fan1_rpm"]))
        self.fan2.set_subtitle(_fmt_rpm(fans["fan2_rpm"]))
        self.duty.set_subtitle(f"{fans['fan1_duty_pct']}%")
        self._sync_mode()

    def on_forced_auto(self):
        self.report(f"A CPU chegou a {LIMIT_C} °C: as ventoinhas voltaram para o automático.")
        self._sync_mode()

    def _sync_mode(self):
        with self.syncing():
            self.checks[self.guard.mode].set_active(True)
        self.speed.set_sensitive(self.guard.mode == "manual")

    def _on_mode(self, check, mode):
        if self.is_syncing or not check.get_active():
            return
        self.report(self.guard.set_mode(mode, int(self.speed.get_value())))
        self._sync_mode()

    def _on_speed(self, scale):
        percent = int(scale.get_value())
        self.app.state["fan"]["duty_pct"] = percent
        if self.guard.mode == "manual":
            self._apply_speed(percent)

    def _send_manual(self, percent):
        # The user may have left manual mode while this send was debounced.
        if self.guard.mode != "manual":
            return
        self.report(self.guard.set_mode("manual", percent))
        self._sync_mode()
        self.app.save_state()
