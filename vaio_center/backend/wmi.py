"""Unprivileged side of the VAIO WMI bridge: runs the pkexec helper and decodes replies."""
import json

from vaio_center.backend import proc

HELPER = "/usr/local/libexec/vaio-wmi-helper"
RPM_CONSTANT = 2156220  # Clevo EC: rpm = constant / tach period

# Codes accepted by WMBB 0x79 sub-command 0x01. Task 15 replaces these labels
# with names derived from live power-limit measurements.
PROFILE_LABELS = {
    0: "Perfil 0",
    1: "Perfil 1",
    2: "Perfil 2",
    5: "Perfil 5",
    6: "Perfil 6",
    7: "Perfil 7",
    8: "Perfil 8",
}


def _helper(*args):
    out, err = proc.run(["pkexec", HELPER, *(str(a) for a in args)])
    return (None if out is None else out.strip()), err


def _write(*args):
    return _helper(*args)[1]


def byte_from_percent(percent):
    return (percent * 255 + 50) // 100


def set_keyboard_color(rgb):
    return _write("kbd-color", rgb)


def events_on():
    return _write("events-on")


def get_event():
    """Last Fn hotkey code from the EC, or None if it could not be read."""
    out, err = _helper("event-get")
    if err:
        return None
    try:
        return int(out, 16)
    except ValueError:
        return None


def set_keyboard_brightness(level):
    return _write("kbd-brightness", level)


def set_fan_duty(duty1, duty2):
    return _write("fan-duty", duty1, duty2)


def set_fan_auto():
    return _write("fan-auto")


def set_charge_limit(stop, start):
    return _write("charge-set", stop, start)


def disable_charge_limit():
    return _write("charge-off")


def set_profile(code):
    if code not in PROFILE_LABELS:
        raise ValueError(f"unknown profile code {code}")
    return _write("profile", code)


def decode_charge(raw):
    return {"enabled": bool(raw & 0xFF), "start": (raw >> 8) & 0xFF, "stop": (raw >> 16) & 0xFF}


def get_charge_limit():
    out, err = _helper("charge-get")
    if err:
        return {"error": err}
    try:
        return decode_charge(int(out, 16))
    except ValueError:
        return {"error": f"unexpected helper output: {out!r}"}


def rpm(period):
    return round(RPM_CONSTANT / period) if period else 0


def decode_fans(raw6f, raw70):
    return {
        "fan1_duty_pct": round((raw6f & 0xFF) * 100 / 255),
        "ec_temp_c": (raw6f >> 8) & 0xFF,
        "fan1_rpm": rpm(raw70 & 0xFFFF),
        "fan2_rpm": rpm((raw70 >> 16) & 0xFFFF),
    }


def read_fans():
    out, err = _helper("fan-read")
    if err:
        return {"error": err}
    try:
        data = json.loads(out)
        return decode_fans(data["0x6f"], data["0x70"])
    except (ValueError, KeyError, TypeError):
        return {"error": f"unexpected helper output: {out!r}"}
