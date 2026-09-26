"""Runtime status the daemon writes and the app reads (what is applied right now)."""
import json
import os
import time
from pathlib import Path

STALE_S = 10  # older than this means the daemon is not running


def status_path():
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return Path(base) / "vaio-center" / "status.json"


def write(data, path=None):
    path = Path(path or status_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps({**data, "updated": time.time()}))
    os.replace(tmp, path)


def read(path=None, now=None):
    try:
        data = json.loads(Path(path or status_path()).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    now = time.time() if now is None else now
    try:
        age = now - data.get("updated", 0)
    except TypeError:  # a non-numeric "updated" means the file is garbled
        return None
    if age > STALE_S:
        return None
    return data
