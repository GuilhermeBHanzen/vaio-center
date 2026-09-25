"""User choices that must survive a reboot, because the EC forgets them."""
import copy
import json
import os
from pathlib import Path

DEFAULTS = {
    "keyboard": {
        "zones": [0x0000C8, 0x0000C8, 0x0000C8],
        "brightness": 255,
        "calibration": [100, 100, 100],
    },
    "profile": None,
    "fan": {"duty_pct": 50},
    "charge": {"enabled": False, "stop": 80, "start": 75},
}


def state_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "vaio-center" / "state.json"


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
    return _merge(DEFAULTS, saved)


def save(data, path=None):
    path = Path(path or state_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)
