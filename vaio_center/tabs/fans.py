"""Fan page: live readings and the fan mode, which the vaio-center daemon applies."""
import time

from gi.repository import Adw, Gtk

from vaio_center.backend import sensors, status, wmi
from vaio_center.fan_policy import AUTO, LIMIT_C, MIN_PCT, MODES
from vaio_center.ui import Debouncer, Page, slider

LABELS = {
    "quiet": ("Silencioso", "25% enquanto a CPU está abaixo de 60 °C; acima disso, o firmware assume."),
    "normal": ("Normal", "O firmware controla as ventoinhas."),
    "aggressive": ("Agressivo", "Mais rápido que o normal: 40% em repouso, 100% a partir de 68 °C."),
    "manual": ("Manual", "Velocidade fixa, definida abaixo."),
    "max": ("Máximo", "As duas ventoinhas a 100%, igual ao Fn+1."),
}
NOT_RUNNING = (
    "O serviço vaio-center não está rodando, então as ventoinhas ficam no automático. "
    "Inicie com: systemctl --user start vaio-center"
)
FORCED = (
    f"A CPU chegou a {LIMIT_C} °C ou a temperatura não pôde ser lida: "
    "o serviço voltou as ventoinhas para o automático. Escolha o modo de novo para retomar."
)
CLICK_GRACE_S = 3  # don't snap the radios back while the daemon is picking up a click


def _fmt_rpm(value):
    return "parada" if value == 0 else f"{value} RPM"


def _fmt_target(target):
    if target == AUTO:
        return "Automático (firmware)"
    return "—" if target is None else f"{target}% fixo"


class FansPage(Page):
    key = "fans"
    title = "Ventoinhas"

    def __init__(self, app, backend=wmi, temps=sensors, status_store=status):
        super().__init__(app)
        self.backend = backend
        self.temps = temps
        self.status_store = status_store
        self._clicked_at = 0.0

        live = self.group("Leitura")
        self.fan1 = self.info_row(live, "Ventoinha 1")
        self.fan2 = self.info_row(live, "Ventoinha 2")
        self.duty = self.info_row(live, "Potência da ventoinha 1")
        self.cpu = self.info_row(live, "Temperatura da CPU")
        self.applied = self.info_row(live, "Aplicado agora")

        control = self.group(
            "Modo",
            f"Aplicado pelo serviço vaio-center, mesmo com o app fechado. "
            f"Manual e Máximo voltam para o automático se a CPU chegar a {LIMIT_C} °C.",
        )
        fan = app.state["fan"]
        self.checks = {}
        leader = None
        for mode in MODES:
            title, subtitle = LABELS[mode]
            check = Gtk.CheckButton()
            if leader is None:
                leader = check
            else:
                check.set_group(leader)
            row = Adw.ActionRow(title=title, subtitle=subtitle)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            control.add(row)
            self.checks[mode] = check
        self.speed = slider(MIN_PCT, 100)
        with self.syncing():
            self.checks[fan["mode"]].set_active(True)
            self.speed.set_value(fan["duty_pct"])
        self.speed.set_sensitive(fan["mode"] == "manual")
        for mode, check in self.checks.items():
            check.connect("toggled", self._on_mode, mode)
        self._save_later = Debouncer(300, self._save_speed)
        self.speed.connect("value-changed", self._on_speed)
        row = Adw.ActionRow(title="Velocidade manual (%)")
        row.add_suffix(self.speed)
        control.add(row)

    def refresh(self):
        cpu = self.temps.cpu_temp_c()
        self.cpu.set_subtitle("—" if cpu is None else f"{cpu:.0f} °C")
        applied = self.status_store.read()
        if applied is None:
            self.report(NOT_RUNNING)
            self.applied.set_subtitle("—")
        else:
            self.report(FORCED if applied.get("forced") else None)
            self.applied.set_subtitle(_fmt_target(applied.get("target")))
            if time.monotonic() - self._clicked_at > CLICK_GRACE_S and applied.get("mode") in self.checks:
                with self.syncing():
                    self.checks[applied["mode"]].set_active(True)
        root = self.get_root()
        if isinstance(root, Gtk.Window) and not root.is_active():
            return  # each read_fans() is a pkexec call; skip it while unfocused
        fans = self.backend.read_fans()
        if "error" in fans:
            self.report(fans["error"])
            return
        self.fan1.set_subtitle(_fmt_rpm(fans["fan1_rpm"]))
        self.fan2.set_subtitle(_fmt_rpm(fans["fan2_rpm"]))
        self.duty.set_subtitle(f"{fans['fan1_duty_pct']}%")

    def _on_mode(self, check, mode):
        if self.is_syncing or not check.get_active():
            return
        fan = self.app.state["fan"]
        fan["mode"] = mode
        fan["duty_pct"] = int(self.speed.get_value())
        fan["rev"] = fan.get("rev", 0) + 1  # tells the daemon this is a fresh choice (clears a latch)
        self.app.save_state()
        self._clicked_at = time.monotonic()
        self.speed.set_sensitive(mode == "manual")

    def _on_speed(self, scale):
        if self.is_syncing:
            return
        self.app.state["fan"]["duty_pct"] = int(scale.get_value())
        self._save_later()

    def _save_speed(self):
        self.app.save_state()
