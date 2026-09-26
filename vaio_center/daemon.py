"""vaio-center background service: Fn backlight hotkeys and fan modes.

Runs as the systemd user unit vaio-center.service. All hardware access goes
through the pkexec helper (backend.wmi). The app talks to it only through files:
it writes state.json (the fan mode it wants), the daemon writes status.json.
"""
import signal
import socket
import sys
import time
import traceback

import gi

gi.require_version("GLib", "2.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

try:
    gi.require_version("GLibUnix", "2.0")
    from gi.repository import GLibUnix  # noqa: E402

    unix_signal_add = GLibUnix.signal_add
except (ImportError, ValueError):
    unix_signal_add = GLib.unix_signal_add

from vaio_center import restore  # noqa: E402
from vaio_center.backend import kbdlevel, sensors, state, status, wmi  # noqa: E402
from vaio_center.backend.wmi import byte_from_percent  # noqa: E402
from vaio_center.fan_policy import AUTO, MAX_MISSES, MIN_PCT, FanPolicy  # noqa: E402

ACPID_SOCKET = "/run/acpid.socket"
KEY_UP, KEY_DOWN, KEY_TOGGLE = 0x81, 0x82, 0x9F
STEP = 51
DEDUPE_S = 0.25
FAN_TICK_S = 2
CONFIG_TICK_S = 1
RECONNECT_S = 5
EVENTS_BACKOFF_START_S = 5
EVENTS_BACKOFF_MAX_S = 300


def is_hotkey_line(line):
    parts = line.split()
    return len(parts) >= 3 and parts[1].startswith("PNP0C14") and parts[2].lower().endswith("d0")


def next_level(code, level, last_on):
    """(new_level, new_last_on) for a backlight hotkey, or None for any other code."""
    if code == KEY_UP:
        new = min(255, level + STEP)
    elif code == KEY_DOWN:
        new = max(0, level - STEP)
    elif code == KEY_TOGGLE:
        new = 0 if level > 0 else (last_on or 255)
    else:
        return None
    return new, (new if new > 0 else (level or last_on))


class Deduper:
    """The EC reports each key press twice; drop a repeat of the same code within the window."""

    def __init__(self, window_s=DEDUPE_S, clock=time.monotonic):
        self.window_s = window_s
        self.clock = clock
        self._code = None
        self._at = float("-inf")

    def accept(self, code, at=None):
        now = self.clock() if at is None else at
        if code == self._code and now - self._at < self.window_s:
            return False
        self._code, self._at = code, now
        return True


class Daemon:
    def __init__(self, wmi=wmi, sensors=sensors, kbd=kbdlevel, store=state, status_store=status,
                 socket_path=ACPID_SOCKET, clock=time.monotonic):
        self.wmi = wmi
        self.sensors = sensors
        self.kbd = kbd
        self.store = store
        self.status_store = status_store
        self.socket_path = socket_path
        self.clock = clock
        self.policy = FanPolicy()
        self.deduper = Deduper()
        self.level = kbd.load()
        self.last_on = self.level or 255
        self.sent = None  # last fan target the EC accepted
        self._mtime = None
        self._fan_key = None
        self._sock = None
        self._buf = ""
        self._sleeping = False
        self._events_pending = False
        self._events_backoff = EVENTS_BACKOFF_START_S
        self._events_retry_at = 0.0
        self._events_failed_logged = False
        self._events_outdated = False
        self.loop = None

    def handle_line(self, line, at=None):
        if not is_hotkey_line(line):
            return
        # I1: reload the shared level before stepping - an app-side slider change
        # (or the previous hotkey) may have moved it since we last looked.
        self.level = self.kbd.load()
        if self.level:
            self.last_on = self.level
        code = self.wmi.get_event()
        if code is None or not self.deduper.accept(code, at):
            return
        result = next_level(code, self.level, self.last_on)
        if result is None:
            return
        new, last_on = result
        if self.wmi.set_keyboard_brightness(new) is None:
            self.level, self.last_on = new, last_on
            self.kbd.save(new)

    def load_config(self, initial=False):
        try:
            st = self.store.state_path().stat()
            stamp = (st.st_mtime_ns, st.st_ino, st.st_size)  # M3: mtime alone can be reused
        except OSError:
            stamp = None
        if not initial and stamp == self._mtime:
            return
        self._mtime = stamp
        try:
            fan = self.store.load()["fan"]
            key = (fan["mode"], fan["duty_pct"], fan.get("rev", 0))
            if initial:
                # A fixed duty is never restored unattended at login.
                mode = "normal" if fan["mode"] in ("manual", "max") else fan["mode"]
                self.policy.set_mode(mode, fan["duty_pct"])
            elif self._fan_key is None or key[2] != self._fan_key[2]:
                # I2: a fresh choice (rev bump) is the only thing allowed to
                # call set_mode - it is the only path that clears a latch.
                self.policy.set_mode(fan["mode"], fan["duty_pct"])
            elif self.policy.mode == fan["mode"] == "manual":
                # A slider-only change while manual is running: apply the new
                # duty without touching forced/misses.
                self.policy.duty_pct = max(MIN_PCT, min(100, int(fan["duty_pct"])))
            # Otherwise this is a duty-only change that doesn't apply right
            # now (e.g. latched max, or the slider for a non-manual mode):
            # ignore it so it cannot resurrect manual/max.
            self._fan_key = key
        except (ValueError, TypeError, KeyError):
            print("vaio-center: invalid fan config, falling back to normal/50", file=sys.stderr)
            self.policy.set_mode("normal", 50)

    def fan_tick(self):
        if self._sleeping:  # M2: nothing to send while suspended
            return GLib.SOURCE_CONTINUE
        try:
            target = self.policy.target(self.sensors.cpu_temp_c())
            if target != self.sent:
                if target == AUTO:
                    error = self.wmi.set_fan_auto()
                else:
                    duty = byte_from_percent(target)
                    error = self.wmi.set_fan_duty(duty, duty)
                self.sent = target if error is None else None
        except Exception:
            print("vaio-center: fan_tick failed, forcing fans to auto", file=sys.stderr)
            traceback.print_exc()
            if self.sent != AUTO:  # R7: don't resend/flip-flop if already auto
                error = self.wmi.set_fan_auto()
                if error:
                    print(f"vaio-center: set_fan_auto failed: {error}", file=sys.stderr)
                self.sent = AUTO if error is None else None
        try:
            forced = self.policy.forced or self.policy.misses >= MAX_MISSES
            self.status_store.write({
                "mode": "normal" if forced else self.policy.mode,
                "forced": forced,
                "target": self.sent,
            })
        except Exception:
            print("vaio-center: status write failed", file=sys.stderr)
            traceback.print_exc()
        return GLib.SOURCE_CONTINUE

    def on_sleep(self, going_down):
        if going_down:
            error = self.wmi.set_fan_auto()
            if error:
                print(f"vaio-center: {error}", file=sys.stderr)
            self.sent = AUTO
            self._sleeping = True
        else:
            self._sleeping = False
            self._reset_events_backoff()
            self._events_on()
            self.sent = None  # re-apply the mode on the next tick

    def _reset_events_backoff(self):
        self._events_backoff = EVENTS_BACKOFF_START_S
        self._events_retry_at = 0.0
        self._events_failed_logged = False
        self._events_outdated = False

    def _events_on(self):
        """Try wmi.events_on(); on failure schedule the next retry (I3 backoff)."""
        error = self.wmi.events_on()
        if not error:
            self._events_pending = False
            self._reset_events_backoff()
            return True
        self._events_pending = True
        if "unknown sub-command" in error:
            if not self._events_outdated:
                print("vaio-center: helper outdated — run: sudo ~/vaio-center/install-root.sh",
                      file=sys.stderr)
                self._events_outdated = True
            return False
        if not self._events_failed_logged:
            print(f"vaio-center: {error}", file=sys.stderr)
            self._events_failed_logged = True
        self._events_retry_at = self.clock() + self._events_backoff
        self._events_backoff = min(self._events_backoff * 2, EVENTS_BACKOFF_MAX_S)
        return False

    def _config_tick(self):
        try:
            if self._events_pending and not self._events_outdated and self.clock() >= self._events_retry_at:
                self._events_on()
            self.load_config()
        except Exception:
            print("vaio-center: config_tick failed", file=sys.stderr)
            traceback.print_exc()
        return GLib.SOURCE_CONTINUE

    def _connect(self):
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
        except OSError:
            GLib.timeout_add_seconds(RECONNECT_S, self._reconnect)
            return
        sock.setblocking(False)
        self._sock, self._buf = sock, ""
        GLib.io_add_watch(sock.fileno(), GLib.PRIORITY_DEFAULT,
                          GLib.IOCondition.IN | GLib.IOCondition.HUP | GLib.IOCondition.ERR,
                          self._on_socket)

    def _reconnect(self):
        self._connect()
        return GLib.SOURCE_REMOVE

    def _on_socket(self, _fd, condition):
        try:
            data = b""
            if condition & GLib.IOCondition.IN:
                try:
                    data = self._sock.recv(4096)
                except BlockingIOError:
                    return GLib.SOURCE_CONTINUE  # no data yet, not a disconnect
                except OSError:
                    data = b""
            if not data:  # acpid went away: retry later
                self._sock.close()
                self._sock = None
                GLib.timeout_add_seconds(RECONNECT_S, self._reconnect)
                return GLib.SOURCE_REMOVE
            at = self.clock()  # R4: stamp with arrival time, not whenever we get around to it
            self._buf += data.decode(errors="replace")
            *lines, self._buf = self._buf.split("\n")
            for line in lines:
                self.handle_line(line, at=at)
            return GLib.SOURCE_CONTINUE
        except Exception:
            print("vaio-center: acpid socket handler failed", file=sys.stderr)
            traceback.print_exc()
            return GLib.SOURCE_CONTINUE

    def _watch_sleep(self):
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        except GLib.Error as exc:
            print(f"vaio-center: {exc}", file=sys.stderr)
            return
        bus.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Manager",
                             "PrepareForSleep", "/org/freedesktop/login1", None,
                             Gio.DBusSignalFlags.NONE,
                             lambda *args: self.on_sleep(args[5].unpack()[0]))

    def _on_signal(self):
        error = self.wmi.set_fan_auto()
        if error:
            print(f"vaio-center: {error}", file=sys.stderr)
        self.loop.quit()
        return GLib.SOURCE_REMOVE

    def run(self):
        for error in restore.restore(self.store.load(), self.wmi, self.kbd):
            print(f"vaio-center: {error}", file=sys.stderr)
        self._reset_events_backoff()
        self._events_on()
        self.load_config(initial=True)
        self.loop = GLib.MainLoop()
        self._connect()
        self._watch_sleep()
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            unix_signal_add(GLib.PRIORITY_DEFAULT, signum, self._on_signal)
        GLib.timeout_add_seconds(CONFIG_TICK_S, self._config_tick)
        GLib.timeout_add_seconds(FAN_TICK_S, self.fan_tick)
        self.fan_tick()
        self.loop.run()
        return 0
