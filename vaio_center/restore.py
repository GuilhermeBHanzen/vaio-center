"""Re-apply the saved EC settings after boot (keyboard, profile, charge limit).

Fans are never restored: a fixed duty without the app running would be unsafe, so
restore first forces them back to auto in case a duty survived an app crash.
"""
from vaio_center.backend import wmi as wmi_backend


def restore(data, wmi=wmi_backend):
    keyboard = data["keyboard"]
    results = [wmi.set_fan_auto()]
    results += [
        wmi.set_zone_color(zone, rgb, calibration)
        for zone, (rgb, calibration) in enumerate(zip(keyboard["zones"], keyboard["calibration"]))
    ]
    results.append(wmi.set_keyboard_brightness(keyboard["brightness"]))
    if data["profile"] is not None:
        results.append(wmi.set_profile(data["profile"]))
    charge = data["charge"]
    if charge["enabled"]:
        results.append(wmi.set_charge_limit(charge["stop"], charge["start"]))
    else:
        results.append(wmi.disable_charge_limit())
    return [error for error in results if error]
