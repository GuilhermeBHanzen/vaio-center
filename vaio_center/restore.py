"""Re-apply the saved EC settings after boot (keyboard, profile, charge limit).

Fans are never restored: a fixed duty without the app running would be unsafe, so
restore first forces them back to auto in case a duty survived an app crash.
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
