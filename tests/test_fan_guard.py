from vaio_center.fan_guard import LIMIT_C, FanGuard


class Temps:
    def __init__(self, value):
        self.value = value

    def cpu_temp_c(self):
        return self.value


def test_starts_in_auto(recorder):
    assert FanGuard(recorder(), Temps(40)).mode == "auto"


def test_manual_is_clamped_to_minimum(recorder):
    wmi = recorder()
    guard = FanGuard(wmi, Temps(40))
    assert guard.set_mode("manual", 10) is None
    assert wmi.calls == [("set_fan_duty", 77, 77)]
    assert guard.mode == "manual"


def test_max_sets_full_duty(recorder):
    wmi = recorder()
    guard = FanGuard(wmi, Temps(40))
    guard.set_mode("max")
    assert wmi.calls == [("set_fan_duty", 255, 255)]
    assert guard.mode == "max"


def test_failed_change_keeps_previous_mode(recorder):
    guard = FanGuard(recorder(error="boom"), Temps(40))
    assert guard.set_mode("max") == "boom"
    assert guard.mode == "auto"


def test_check_forces_auto_when_hot(recorder):
    wmi = recorder()
    guard = FanGuard(wmi, Temps(LIMIT_C))
    guard.set_mode("manual", 40)
    assert guard.check() is True
    assert guard.mode == "auto"
    assert wmi.calls[-1] == ("set_fan_auto",)


def test_check_ignores_auto_mode_cool_cpu_and_missing_sensor(recorder):
    wmi = recorder()
    assert FanGuard(wmi, Temps(99)).check() is False
    cool = FanGuard(wmi, Temps(60))
    cool.set_mode("max")
    assert cool.check() is False
    blind = FanGuard(wmi, Temps(None))
    blind.set_mode("max")
    assert blind.check() is False
    assert ("set_fan_auto",) not in wmi.calls


def test_release_only_acts_outside_auto(recorder):
    wmi = recorder()
    guard = FanGuard(wmi, Temps(40))
    assert guard.release() is None
    assert wmi.calls == []
    guard.set_mode("max")
    guard.release()
    assert wmi.calls[-1] == ("set_fan_auto",)
    assert guard.mode == "auto"


def test_check_forces_auto_after_two_missing_readings(recorder):
    wmi = recorder()
    temps = Temps(None)
    guard = FanGuard(wmi, temps)
    guard.set_mode("manual", 40)
    assert guard.check() is False
    assert guard.check() is True
    assert guard.mode == "auto"
    assert wmi.calls[-1] == ("set_fan_auto",)


def test_valid_reading_resets_missing_sensor_count(recorder):
    wmi = recorder()
    temps = Temps(None)
    guard = FanGuard(wmi, temps)
    guard.set_mode("max")
    assert guard.check() is False
    temps.value = 60
    assert guard.check() is False
    temps.value = None
    assert guard.check() is False
    assert guard.mode == "max"
    assert ("set_fan_auto",) not in wmi.calls
