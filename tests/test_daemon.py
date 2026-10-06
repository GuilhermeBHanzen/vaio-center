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
        return {
            "fan": dict(self.fan),
            "keyboard": {"color": "#ffffff"},
            "profile": None,
            "charge": {"enabled": False, "stop": 80, "start": 70},
        }


class FakeClock:
    """Manually-advanced monotonic clock for backoff/dedupe tests."""

    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class FakeSocket:
    def __init__(self, data):
        self.data = data

    def recv(self, n):
        data, self.data = self.data, b""
        return data

    def close(self):
        pass


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


def test_handle_line_reloads_level_from_kbd_store_before_stepping(tmp_path):
    """I1: an app-side slider change must be picked up before the next Fn press."""
    wmi = FakeWmi(event=0x81)
    d = make(tmp_path, wmi=wmi, level=255)
    d.kbd.level = 51  # the app changed the level directly, bypassing the daemon
    d.handle_line(LINE)
    assert ("set_keyboard_brightness", 102) in wmi.calls
    assert d.level == 102


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
    assert d.sent == AUTO  # R7: set_fan_auto succeeded, so it is not resent next tick


def test_fan_tick_status_write_failure_does_not_flip_flop(tmp_path):
    """R7: a status_store.write() failure must not undo the fan target already sent."""

    class RaisingStatus:
        def write(self, data):
            raise RuntimeError("disk full")

    wmi = FakeWmi()
    d = make(tmp_path, wmi=wmi, fan={"mode": "max", "duty_pct": 50, "rev": 0}, temp=50)
    d.status_store = RaisingStatus()
    d.policy.set_mode("max")
    d.fan_tick()
    d.fan_tick()
    assert wmi.calls.count(("set_fan_duty", 255, 255)) == 1
    assert d.sent == 100


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


def test_duty_only_change_does_not_resurrect_latched_max(tmp_path):
    """I2(a): a slider-only change must not clear a 90C latch."""
    d = make(tmp_path, fan={"mode": "max", "duty_pct": 50, "rev": 0})
    d.load_config()
    d.policy.target(95)  # crosses LIMIT_C -> latches forced
    assert d.policy.forced
    d.store.fan = {"mode": "max", "duty_pct": 80, "rev": 0}
    d.store.path.write_text(json.dumps({"x": 1}))
    os.utime(d.store.path, ns=(1, 1))
    d.load_config()
    assert d.policy.forced
    assert d.policy.mode == "max"


def test_duty_only_change_applies_new_duty_when_manual(tmp_path):
    """I2(b): a slider-only change while manual is running just updates the duty."""
    d = make(tmp_path, fan={"mode": "manual", "duty_pct": 40, "rev": 0})
    d.load_config()
    assert d.policy.mode == "manual"
    d.store.fan = {"mode": "manual", "duty_pct": 90, "rev": 0}
    d.store.path.write_text(json.dumps({"x": 1}))
    os.utime(d.store.path, ns=(1, 1))
    d.load_config()
    assert d.policy.duty_pct == 90
    assert not d.policy.forced


def test_rev_bump_clears_latch(tmp_path):
    """I2(c): a fresh choice (rev bump) still clears a latch via set_mode."""
    d = make(tmp_path, fan={"mode": "max", "duty_pct": 50, "rev": 0})
    d.load_config()
    d.policy.target(95)
    assert d.policy.forced
    d.store.fan = {"mode": "max", "duty_pct": 50, "rev": 1}
    d.store.path.write_text(json.dumps({"x": 1}))
    os.utime(d.store.path, ns=(1, 1))
    d.load_config()
    assert not d.policy.forced


def test_load_config_invalid_mode_falls_back_to_normal(tmp_path):
    """R6: an unreadable/invalid fan config must not crash load_config."""
    d = make(tmp_path, fan={"mode": "not-a-mode", "duty_pct": 50, "rev": 0})
    d.load_config(initial=True)
    assert d.policy.mode == "normal"
    assert d.policy.duty_pct == 50


def test_load_config_detects_content_change_with_same_mtime(tmp_path):
    """M3: same-second rewrites must still be detected via inode/size, not mtime alone."""
    d = make(tmp_path, fan={"mode": "normal", "duty_pct": 50, "rev": 0})
    os.utime(d.store.path, ns=(1, 1))
    d.load_config(initial=True)
    d.store.fan = {"mode": "quiet", "duty_pct": 50, "rev": 1}
    d.store.path.write_text(json.dumps({"x": 1}))
    os.utime(d.store.path, ns=(1, 1))  # identical mtime despite the content change
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
    assert d._sleeping is True
    d.on_sleep(False)
    assert ("events_on",) in wmi.calls
    assert d.sent is None
    assert d._sleeping is False


def test_fan_tick_skips_sending_while_sleeping(tmp_path):
    """M2: fan_tick must not send anything while suspended, but still keeps ticking."""
    wmi = FakeWmi()
    d = make(tmp_path, wmi=wmi, fan={"mode": "max", "duty_pct": 50, "rev": 0})
    d.load_config(initial=True)
    d.on_sleep(True)
    wmi.calls.clear()
    result = d.fan_tick()
    assert result == daemon.GLib.SOURCE_CONTINUE
    assert wmi.calls == []


def test_resume_events_on_failure_is_retried_by_config_tick(tmp_path):
    wmi = FakeWmi(error="boom")
    d = make(tmp_path, wmi=wmi)
    clock = FakeClock(0.0)
    d.clock = clock
    d.on_sleep(False)
    assert d._events_pending is True
    wmi.error = None
    clock.advance(5.0)  # I3: config_tick only retries once the backoff has elapsed
    d._config_tick()
    assert d._events_pending is False


def test_events_on_backoff_doubles_and_logs_first_failure_only(tmp_path, capsys):
    wmi = FakeWmi(error="boom")
    d = make(tmp_path, wmi=wmi)
    clock = FakeClock(0.0)
    d.clock = clock
    d._reset_events_backoff()
    assert d._events_on() is False
    assert d._events_backoff == 10
    assert d._events_retry_at == 5.0
    assert "boom" in capsys.readouterr().err
    d._config_tick()  # not yet due: must not retry
    assert wmi.calls.count(("events_on",)) == 1
    clock.advance(5.0)
    d._config_tick()  # due now: retries, still fails
    assert wmi.calls.count(("events_on",)) == 2
    assert capsys.readouterr().err == ""  # same streak: no duplicate log
    assert d._events_backoff == 20


def test_events_on_success_resets_backoff(tmp_path):
    wmi = FakeWmi(error="boom")
    d = make(tmp_path, wmi=wmi)
    clock = FakeClock(0.0)
    d.clock = clock
    d._reset_events_backoff()
    d._events_on()
    assert d._events_backoff == 10
    wmi.error = None
    assert d._events_on() is True
    assert d._events_backoff == 5
    assert d._events_pending is False


def test_events_on_unknown_subcommand_stops_retrying_until_resume(tmp_path, capsys):
    wmi = FakeWmi(error="vaio-wmi-helper: unknown sub-command 'events-on'")
    d = make(tmp_path, wmi=wmi)
    clock = FakeClock(0.0)
    d.clock = clock
    d._reset_events_backoff()
    assert d._events_on() is False
    assert "helper outdated" in capsys.readouterr().err
    clock.advance(1000)
    d._config_tick()
    assert wmi.calls.count(("events_on",)) == 1  # never retried: helper is outdated
    d.on_sleep(False)  # resume resets state and tries again
    assert wmi.calls.count(("events_on",)) == 2


def test_dedupe_uses_socket_arrival_time_not_processing_time(tmp_path):
    """R4: two lines arriving 0.1s apart dedupe even if handling them is slow."""
    wmi = FakeWmi(event=0x81)
    d = make(tmp_path, wmi=wmi, level=153)  # d.deduper.clock jumps by 1.0 per call if used
    d.handle_line(LINE, at=0.0)
    d.handle_line(LINE, at=0.1)
    assert wmi.calls.count(("get_event",)) == 2
    assert wmi.calls.count(("set_keyboard_brightness", 204)) == 1


def test_on_socket_stamps_lines_with_arrival_clock(tmp_path):
    wmi = FakeWmi(event=0x81)
    d = make(tmp_path, wmi=wmi, level=153)
    stamped = []
    d.handle_line = lambda line, at=None: stamped.append((line, at))
    d.clock = lambda: 42.0
    d._sock = FakeSocket(f"{LINE}\n".encode())
    d._on_socket(0, daemon.GLib.IOCondition.IN)
    assert stamped == [(LINE, 42.0)]


def make_restore(tmp_path, error="Sem autorizacao do polkit"):
    wmi = FakeWmi(error=error)
    d = make(tmp_path, wmi=wmi)
    scheduled = []
    d._schedule = lambda delay, func: scheduled.append((delay, func))
    return d, wmi, scheduled


def test_restore_retry_delays_double_up_to_cap(tmp_path):
    d, _wmi, scheduled = make_restore(tmp_path)
    for _ in range(9):
        assert d._restore_attempt() == daemon.GLib.SOURCE_REMOVE
    assert [delay for delay, _func in scheduled] == [5, 10, 20, 40, 60, 60, 60, 60, 60]
    assert all(func == d._restore_attempt for _delay, func in scheduled)


def test_restore_success_stops_retrying_and_retries_events(tmp_path):
    d, wmi, scheduled = make_restore(tmp_path)
    d._restore_attempt()
    assert len(scheduled) == 1
    wmi.error = None
    d._events_backoff, d._events_retry_at = 300, 999.0  # events_on backoff still waiting
    wmi.calls.clear()
    assert d._restore_attempt() == daemon.GLib.SOURCE_REMOVE
    assert len(scheduled) == 1  # no further retry
    assert ("set_keyboard_color", "#ffffff") in wmi.calls
    assert ("events_on",) in wmi.calls
    assert d._events_pending is False
    assert d._events_backoff == daemon.EVENTS_BACKOFF_START_S


def test_restore_first_try_success_schedules_nothing_and_stays_quiet(tmp_path, capsys):
    d, wmi, scheduled = make_restore(tmp_path, error=None)
    assert d._restore_attempt() == daemon.GLib.SOURCE_REMOVE
    assert scheduled == []
    assert ("events_on",) not in wmi.calls  # run() does the first events_on itself
    assert capsys.readouterr().err == ""


def test_restore_gives_up_after_10_attempts(tmp_path):
    d, _wmi, scheduled = make_restore(tmp_path)
    for _ in range(10):
        d._restore_attempt()
    assert len(scheduled) == 9  # the 10th attempt is the last: no 11th scheduled
    assert d._restore_attempts == 10


def test_restore_logs_only_first_attempt_and_give_up(tmp_path, capsys):
    d, _wmi, _scheduled = make_restore(tmp_path)
    d._restore_attempt()
    assert "polkit" in capsys.readouterr().err
    for _ in range(8):  # attempts 2..9
        d._restore_attempt()
    assert capsys.readouterr().err == ""
    d._restore_attempt()  # attempt 10: gives up
    err = capsys.readouterr().err
    assert "polkit" in err
    assert "giving up" in err


def test_resume_does_not_rerun_restore(tmp_path):
    d, wmi, scheduled = make_restore(tmp_path, error=None)
    d.on_sleep(True)
    wmi.calls.clear()
    d.on_sleep(False)
    assert ("set_keyboard_color", "#ffffff") not in wmi.calls
    assert scheduled == []
