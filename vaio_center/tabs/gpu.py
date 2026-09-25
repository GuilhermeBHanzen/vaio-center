"""Read-only dGPU page. Never wakes a suspended GPU (see backend.gpu)."""
from vaio_center.backend import gpu
from vaio_center.ui import Page


def _fmt(value, unit):
    return "—" if value is None else f"{value}{unit}"


class GpuPage(Page):
    key = "gpu"
    title = "GPU"

    def __init__(self, app, backend=gpu):
        super().__init__(app)
        self.backend = backend
        group = self.group("NVIDIA", "Somente leitura. A troca de modo da GPU não faz parte deste app.")
        self.status_row = self.info_row(group, "Estado")
        self.name = self.info_row(group, "Placa")
        self.temp = self.info_row(group, "Temperatura")
        self.util = self.info_row(group, "Uso")
        self.power = self.info_row(group, "Consumo")
        self.memory = self.info_row(group, "Memória")
        self.pstate = self.info_row(group, "P-state")
        self.details = (self.name, self.temp, self.util, self.power, self.memory, self.pstate)

    def refresh(self):
        status = self.backend.get_status()
        if self.report(status.get("error")):
            return
        if status["suspended"]:
            self.status_row.set_subtitle("Suspensa (economizando energia)")
            for row in self.details:
                row.set_subtitle("—")
            return
        self.status_row.set_subtitle("Ativa")
        self.name.set_subtitle(status["name"])
        self.temp.set_subtitle(_fmt(status["temp_c"], " °C"))
        self.util.set_subtitle(_fmt(status["util_pct"], "%"))
        self.power.set_subtitle(_fmt(status["power_w"], " W"))
        self.memory.set_subtitle(f"{_fmt(status['mem_used_mib'], '')} / {_fmt(status['mem_total_mib'], ' MiB')}")
        self.pstate.set_subtitle(status["pstate"])
