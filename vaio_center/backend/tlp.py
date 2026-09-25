"""TLP power mode, kept in sync with HyDE's waybar custom/tlpinfo module."""
import os
from pathlib import Path

from vaio_center.backend import proc

MODES = ("performance", "balanced", "power-saver")


def mode_file():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(base) / "hyde" / "tlp-mode"


def parse_profile(text):
    for line in text.splitlines():
        if line.startswith("TLP profile"):
            return line.split("=", 1)[1].strip().split("/")[0]
    return None


def get_mode():
    try:
        mode = mode_file().read_text().strip()
    except OSError:
        mode = ""
    if mode in MODES:
        return mode
    out, err = proc.run(["tlp-stat", "-s"])
    return None if err else parse_profile(out)


def set_mode(mode):
    """Same command sequence as the waybar menu. Returns None, CANCELLED or an error."""
    if mode not in MODES:
        raise ValueError(f"unknown TLP mode {mode!r}")
    _out, err = proc.run(["pkexec", "tlp", mode], timeout=120)
    if err:
        return err
    path = mode_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(mode + "\n")
    proc.run(["pkill", "-RTMIN+3", "waybar"])
    return None
