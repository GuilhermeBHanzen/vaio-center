"""Battery status from UPower."""
from vaio_center.backend import proc

DEVICE = "/org/freedesktop/UPower/devices/battery_BAT0"

FIELDS = {
    "state": "state",
    "percentage": "percentage",
    "capacity": "health",
    "energy-full": "energy_full",
    "energy-full-design": "energy_full_design",
    "energy-rate": "rate",
    "time to empty": "time_to_empty",
    "time to full": "time_to_full",
}
NUMERIC = {"percentage", "health", "energy_full", "energy_full_design", "rate"}


def parse_upower(text):
    info = {}
    for line in text.splitlines():
        key, sep, value = line.strip().partition(":")
        name = FIELDS.get(key)
        if not sep or name is None:
            continue
        value = value.strip()
        info[name] = float(value.split()[0].rstrip("%")) if name in NUMERIC else value
    return info


def get_status():
    out, err = proc.run(["upower", "-i", DEVICE])
    if err:
        return {"error": err}
    return parse_upower(out)
