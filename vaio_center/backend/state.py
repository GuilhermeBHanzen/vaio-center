"""User choices that must survive a reboot, because the EC forgets them."""
import copy
import json
import os
from pathlib import Path

FAN_MODES = ("quiet", "normal", "aggressive", "manual", "max")
CHARGE_SOURCES = ("bios", "app")  # who owns the charge limit: the firmware, or this app

DEFAULTS = {
    "keyboard": {"color": 0x0000C8},
    "profile": None,
    "fan": {"mode": "normal", "duty_pct": 50, "rev": 0},
    "charge": {"source": "bios", "enabled": False, "stop": 80, "start": 75},
}


def state_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "vaio-center" / "state.json"


def _migrate(saved):
    """Map v1 files (per-zone colors, no fan mode) onto the v1.1 schema."""
    keyboard = saved.get("keyboard")
    if isinstance(keyboard, dict) and "color" not in keyboard:
        zones = keyboard.get("zones")
        if isinstance(zones, list) and zones and isinstance(zones[0], int):
            keyboard["color"] = zones[0]
    fan = saved.get("fan")
    if isinstance(fan, dict) and fan.get("mode") not in FAN_MODES:
        fan["mode"] = "normal"
    charge = saved.get("charge")
    if isinstance(charge, dict) and charge.get("source") not in CHARGE_SOURCES:
        charge["source"] = "bios"
    return saved


def _merge(defaults, saved):
    merged = copy.deepcopy(defaults)
    for key, value in saved.items():
        if key not in merged:
            continue
        if isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load(path=None):
    path = Path(path or state_path())
    try:
        saved = json.loads(path.read_text())
    except (OSError, ValueError):
        return copy.deepcopy(DEFAULTS)
    if not isinstance(saved, dict):
        return copy.deepcopy(DEFAULTS)
    saved = _migrate(saved)
    return _merge(DEFAULTS, saved)


def save(data, path=None):
    path = Path(path or state_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)
