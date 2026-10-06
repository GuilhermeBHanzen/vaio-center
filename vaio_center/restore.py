"""Re-apply the saved EC settings after boot (keyboard, profile, charge limit).

The vaio-center daemon owns fan modes from here on (see daemon.load_config):
it re-applies the saved mode itself once running. This restore step never sets
a fan duty - it only forces the fans back to auto first, in case a fixed duty
survived a crash from before the daemon started.
"""
from vaio_center.backend import kbdlevel
from vaio_center.backend import wmi as wmi_backend


def restore(data, wmi=wmi_backend, kbd=kbdlevel):
    calls = [
        (wmi.set_fan_auto,),
        (wmi.set_keyboard_color, data["keyboard"]["color"]),
        (wmi.set_keyboard_brightness, kbd.load()),
    ]
    if data["profile"] is not None:
        calls.append((wmi.set_profile, data["profile"]))
    charge = data["charge"]
    # In BIOS mode the firmware owns the charge limit: the app never writes it.
    if charge.get("source") != "bios":
        if charge["enabled"]:
            calls.append((wmi.set_charge_limit, charge["stop"], charge["start"]))
        else:
            calls.append((wmi.disable_charge_limit,))
    errors = []
    for func, *args in calls:
        # A bad saved value (ValueError) must not stop the remaining settings.
        try:
            error = func(*args)
        except ValueError as exc:
            error = str(exc)
        if error:
            errors.append(error)
    return errors
