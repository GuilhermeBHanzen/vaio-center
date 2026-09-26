"""Keyboard backlight level (0-255), shared by the app and the daemon; last writer wins."""
import os
from pathlib import Path

DEFAULT = 255


def level_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "vaio-center" / "kbd-brightness"


def load(path=None):
    try:
        value = int(Path(path or level_path()).read_text().strip())
    except (OSError, ValueError):
        return DEFAULT
    return max(0, min(255, value))


def save(level, path=None):
    path = Path(path or level_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(f"{int(level)}\n")
    os.replace(tmp, path)
