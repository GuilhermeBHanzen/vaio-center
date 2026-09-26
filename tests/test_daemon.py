import json
import os

from vaio_center import daemon
from vaio_center.fan_policy import AUTO


class FakeWmi:
    def __init__(self, event=0x81, error=None):
        self.calls = []
        self.event = event
        self.error = error

    def get_event(self):
        self.calls.append(("get_event",))
        return self.event

    def __getattr__(self, name):
        def method(*args):
            self.calls.append((name, *args))
            return self.error

        return method


class FakeLevels:
    def __init__(self, level=255):
        self.level = level
        self.saved = []

    def load(self):
        return self.level

    def save(self, level):
        self.saved.append(level)


class FakeTemps:
    def __init__(self, temp=50):
        self.temp = temp

    def cpu_temp_c(self):
        return self.temp


class FakeStatus:
    def __init__(self):
        self.written = []

    def write(self, data):
        self.written.append(data)


class FakeStore:
    def __init__(self, path, fan):
        self.path = path
        self.fan = fan

    def state_path(self):
        return self.path

    def load(self):
        return {"fan": dict(self.fan)}


LINE = "wmi PNP0C14:01 000000d0 00000000"


def make(tmp_path, wmi=None, fan=None, level=255, temp=50):
    path = tmp_path / "state.json"
    path.write_text("{}")
    store = FakeStore(path, fan or {"mode": "normal", "duty_pct": 50, "rev": 0})
    clock = iter(float(i) for i in range(1000))
    d = daemon.Daemon(
        wmi=wmi or FakeWmi(),
        sensors=FakeTemps(temp),
        kbd=FakeLevels(level),
        store=store,
        status_store=FakeStatus(),
    )
    d.deduper = daemon.Deduper(clock=lambda: next(clock))
    return d


def test_is_hotkey_line():
    assert daemon.is_hotkey_line(LINE)
    assert not daemon.is_hotkey_line("button/power PBTN 00000080 00000000")
    assert not daemon.is_hotkey_line("wmi PNP0C14:01 000000d1 00000000")
    assert not daemon.is_hotkey_line("")


def test_next_level():
    assert daemon.next_level(0x81, 153, 153) == (204, 204)
    assert daemon.next_level(0x81, 255, 255) == (255, 255)
    assert daemon.next_level(0x82, 51, 51) == (0, 51)
    assert daemon.next_level(0x9F, 153, 153) == (0, 153)
    assert daemon.next_level(0x9F, 0, 153) == (153, 153)
    assert daemon.next_level(0x9F, 0, 0) == (255, 255)
    assert daemon.next_level(0x70, 100, 100) is None


def test_deduper_drops_repeats_inside_window():
    times = iter([0.0, 0.1, 0.5, 0.55])
    dedupe = daemon.Deduper(window_s=0.25, clock=lambda: next(times))
    assert dedupe.accept(0x81)
    assert not dedupe.accept(0x81)
    assert dedupe.accept(0x81)
    assert dedupe.accept(0x82)


def test_hotkey_up_sets_and_persists_level(tmp_path):
    wmi = FakeWmi(event=0x81)
    d = make(tmp_path, wmi=wmi, level=153)
    d.handle_line(LINE)
    assert ("set_keyboard_brightness", 204) in wmi.calls
    assert d.kbd.saved == [204]


def test_hotkey_ignored_for_other_lines_and_failed_writes(tmp_path):
    wmi = FakeWmi(event=0x81, error="boom")
    d = make(tmp_path, wmi=wmi, level=153)
    d.handle_line("button/power PBTN 00000080 00000000")
    assert wmi.calls == []
    d.handle_line(LINE)
    assert d.kbd.saved == []
    assert d.level == 153


def test_fan_tick_sends_only_changes_and_writes_status(tmp_path):
    wmi = FakeWmi()
    d = make(tmp_path, wmi=wmi, fan={"mode": "aggressive", "duty_pct": 50, "rev": 0}, temp=70)
    d.load_config(initial=True)
    d.fan_tick()
    d.fan_tick()
    assert wmi.calls.count(("set_fan_duty", 255, 255)) == 1
    assert d.status_store.written[-1] == {"mode": "aggressive", "forced": False, "target": 100}


def test_fan_tick_forced_when_temps_unreadable(tmp_path):
    wmi = FakeWmi()
    d = make(tmp_path, wmi=wmi, fan={"mode": "aggressive", "duty_pct": 50, "rev": 0}, temp=None)
    d.load_config(initial=True)
    d.fan_tick()
    d.fan_tick()
    assert d.status_store.written[-1] == {"mode": "normal", "forced": True, "target": AUTO}


def test_fan_tick_exception_forces_auto_and_keeps_ticking(tmp_path):
    class RaisingTemps:
        def cpu_temp_c(self):
            raise RuntimeError("boom")

    wmi = FakeWmi()
    d = make(tmp_path, wmi=wmi)
    d.sensors = RaisingTemps()
    result = d.fan_tick()
    assert result == daemon.GLib.SOURCE_CONTINUE
    assert ("set_fan_auto",) in wmi.calls
    assert d.sent is None


def test_manual_and_max_are_not_restored_at_start(tmp_path):
    d = make(tmp_path, fan={"mode": "max", "duty_pct": 50, "rev": 3})
    d.load_config(initial=True)
    assert d.policy.mode == "normal"


def test_config_change_applies_new_choice(tmp_path):
    d = make(tmp_path, fan={"mode": "normal", "duty_pct": 50, "rev": 0})
    d.load_config(initial=True)
    d.store.fan = {"mode": "quiet", "duty_pct": 50, "rev": 1}
    d.store.path.write_text(json.dumps({"x": 1}))
    os.utime(d.store.path, ns=(1, 1))
    d.load_config()
    assert d.policy.mode == "quiet"


def test_failed_send_retries_next_tick(tmp_path):
    wmi = FakeWmi(error="boom")
    d = make(tmp_path, wmi=wmi)
    d.policy.set_mode("max")
    d.fan_tick()
    assert d.sent is None
    wmi.error = None
    d.fan_tick()
    assert d.sent == 100


def test_sleep_hands_fans_to_ec_and_resume_reenables_events(tmp_path):
    wmi = FakeWmi()
    d = make(tmp_path, wmi=wmi)
    d.sent = 100
    d.on_sleep(True)
    assert ("set_fan_auto",) in wmi.calls
    assert d.sent == AUTO
    d.on_sleep(False)
    assert ("events_on",) in wmi.calls
    assert d.sent is None


def test_resume_events_on_failure_is_retried_by_config_tick(tmp_path):
    wmi = FakeWmi(error="boom")
    d = make(tmp_path, wmi=wmi)
    d.on_sleep(False)
    assert d._events_pending is True
    wmi.error = None
    d._config_tick()
    assert d._events_pending is False
