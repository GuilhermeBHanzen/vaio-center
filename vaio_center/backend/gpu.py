"""Read-only NVIDIA dGPU status that never wakes a runtime-suspended GPU."""
from pathlib import Path

from vaio_center.backend import proc

PCI_RUNTIME = "/sys/bus/pci/devices/0000:01:00.0/power/runtime_status"
QUERY = "name,temperature.gpu,utilization.gpu,power.draw,memory.used,memory.total,pstate"


def runtime_status(path=PCI_RUNTIME):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def _num(text, cast):
    try:
        return cast(text)
    except ValueError:
        return None


def parse_query(line):
    name, temp, util, power, used, total, pstate = (field.strip() for field in line.split(","))
    return {
        "name": name,
        "temp_c": _num(temp, int),
        "util_pct": _num(util, int),
        "power_w": _num(power, float),
        "mem_used_mib": _num(used, int),
        "mem_total_mib": _num(total, int),
        "pstate": pstate,
    }


def get_status():
    if runtime_status() == "suspended":
        return {"suspended": True}
    out, err = proc.run(["nvidia-smi", f"--query-gpu={QUERY}", "--format=csv,noheader,nounits"])
    if err:
        return {"error": err}
    try:
        status = parse_query(out.splitlines()[0])
    except (ValueError, IndexError):
        return {"error": f"unexpected nvidia-smi output: {out!r}"}
    status["suspended"] = False
    return status
