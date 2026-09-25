"""Battery status page (read-only; the charge limit lives on the Desempenho page)."""
from vaio_center.backend import battery
from vaio_center.ui import Page

STATES = {
    "charging": "Carregando",
    "discharging": "Descarregando",
    "fully-charged": "Carregada",
    "pending-charge": "Aguardando (limite de carga ativo)",
    "pending-discharge": "Aguardando descarga",
    "empty": "Vazia",
}


class BatteryPage(Page):
    key = "battery"
    title = "Bateria"

    def __init__(self, app, backend=battery):
        super().__init__(app)
        self.backend = backend
        group = self.group("Status")
        self.charge = self.info_row(group, "Carga")
        self.status = self.info_row(group, "Estado")
        self.health = self.info_row(group, "Saúde (capacidade atual / original)")
        self.energy = self.info_row(group, "Capacidade")
        self.time = self.info_row(group, "Tempo restante")
        self.rate = self.info_row(group, "Consumo")

    def refresh(self):
        info = self.backend.get_status()
        if self.report(info.get("error")):
            return
        self.charge.set_subtitle(f"{info['percentage']:.0f}%" if "percentage" in info else "—")
        self.status.set_subtitle(STATES.get(info.get("state"), info.get("state", "—")))
        self.health.set_subtitle(f"{info['health']:.0f}%" if "health" in info else "—")
        if "energy_full" in info and "energy_full_design" in info:
            self.energy.set_subtitle(f"{info['energy_full']:.1f} de {info['energy_full_design']:.1f} Wh")
        self.time.set_subtitle(info.get("time_to_empty") or info.get("time_to_full") or "—")
        self.rate.set_subtitle(f"{info['rate']:.1f} W" if "rate" in info else "—")
