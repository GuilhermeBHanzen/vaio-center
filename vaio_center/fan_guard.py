"""Owns the fan mode and hands control back to the EC whenever a fixed duty is unsafe."""
from vaio_center.backend import sensors as sensors_backend
from vaio_center.backend import wmi as wmi_backend
from vaio_center.backend.wmi import byte_from_percent

LIMIT_C = 90
MIN_PCT = 30
MAX_MISSES = 2  # consecutive failed temperature reads before failing closed


class FanGuard:
    def __init__(self, wmi=wmi_backend, sensors=sensors_backend):
        self.wmi = wmi
        self.sensors = sensors
        self.mode = "auto"
        self.misses = 0

    def set_mode(self, mode, duty_pct=50):
        if mode == "auto":
            error = self.wmi.set_fan_auto()
        elif mode == "max":
            error = self.wmi.set_fan_duty(255, 255)
        elif mode == "manual":
            duty = byte_from_percent(max(MIN_PCT, min(100, duty_pct)))
            error = self.wmi.set_fan_duty(duty, duty)
        else:
            raise ValueError(f"unknown fan mode {mode!r}")
        if error is None:
            self.mode = mode
        return error

    def check(self):
        """Periodic safety check. Returns True when it just switched the fans back to auto."""
        if self.mode == "auto":
            return False
        temp = self.sensors.cpu_temp_c()
        if temp is None:
            # Fail closed: a blind fixed duty is as unsafe as a hot one.
            self.misses += 1
            if self.misses < MAX_MISSES:
                return False
        else:
            self.misses = 0
            if temp < LIMIT_C:
                return False
        forced = self.set_mode("auto") is None
        if forced:
            self.misses = 0
        return forced

    def release(self):
        return None if self.mode == "auto" else self.set_mode("auto")
