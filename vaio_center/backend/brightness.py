"""Screen brightness through brightnessctl (goes via logind, no root needed)."""
from vaio_center.backend import proc


def parse_machine(line):
    device, _cls, _current, percent, _maximum = line.strip().split(",")
    return {"device": device, "percent": int(percent.rstrip("%"))}


def get_percent():
    out, err = proc.run(["brightnessctl", "-m"])
    if err:
        return None
    try:
        return parse_machine(out)["percent"]
    except ValueError:
        return None


def set_percent(percent):
    percent = max(1, min(100, int(percent)))  # 0% would black out the panel
    return proc.run(["brightnessctl", "-q", "set", f"{percent}%"])[1]
