#!/usr/bin/python3 -I
"""Root-only bridge from vaio-center to the VAIO FH15 embedded controller.

Started through pkexec. Accepts a fixed set of sub-commands with range-checked
integer arguments, packs them into \\_SB.WMI.WMBB calls (Clevo WMI interface,
GUID ABBC0F6D-8EA1-11D1-00A0-C90629100000) and executes them via acpi_call.
It never forwards caller-supplied ACPI paths or raw arguments.

Sub-commands:
  kbd-color RGB      - Set keyboard color (single zone, RGB as 0xRRGGBB, sent as B-R-G)
  events-on          - Enable Fn key hotkey events
  event-get          - Get a pending hotkey event
"""
import fcntl
import json
import os
import sys

ACPI_CALL = "/proc/acpi/call"
LOCK_FILE = "/run/vaio-wmi-helper.lock"
METHOD = "\\_SB.WMI.WMBB"

KBD = 0x67
FAN_SET = 0x68
FAN_AUTO = 0x69
SET_EVENTS = 0x46
GET_EVENT = 0x01
CHARGE_SET = 0x76
CHARGE_GET = 0x77
OPT = 0x79
FAN_READS = (0x6F, 0x70)
PROFILES = (0, 1, 2, 5, 6, 7, 8)
MIN_DUTY = 64

ARITY = {
    "kbd-color": 1,
    "kbd-brightness": 1,
    "fan-duty": 2,
    "fan-auto": 0,
    "fan-read": 0,
    "events-on": 0,
    "event-get": 0,
    "charge-set": 2,
    "charge-off": 0,
    "charge-get": 0,
    "profile": 1,
}


class UsageError(ValueError):
    pass


def _int(text, lo, hi, name):
    try:
        value = int(text, 0)
    except ValueError:
        raise UsageError(f"{name} must be an integer, got {text!r}") from None
    if not lo <= value <= hi:
        raise UsageError(f"{name} must be in {lo}..{hi}, got {value}")
    return value


def encode(args):
    """Translate CLI args into the (cmd, arg) WMBB calls to perform, in order."""
    if not args:
        raise UsageError("missing sub-command")
    op, rest = args[0], args[1:]
    if op not in ARITY:
        raise UsageError(f"unknown sub-command {op!r}")
    if len(rest) != ARITY[op]:
        raise UsageError(f"{op} takes {ARITY[op]} argument(s)")

    if op == "kbd-color":
        rgb = _int(rest[0], 0, 0xFFFFFF, "rgb")
        red, green, blue = rgb >> 16 & 0xFF, rgb >> 8 & 0xFF, rgb & 0xFF
        # Single-zone keyboard: only zone 0 has an effect, in B-R-G byte order.
        return [(KBD, 0xF0000000 | blue << 16 | red << 8 | green)]
    if op == "events-on":
        return [(SET_EVENTS, 0)]
    if op == "event-get":
        return [(GET_EVENT, 0)]
    if op == "kbd-brightness":
        return [(KBD, 0xF4000000 | _int(rest[0], 0, 255, "brightness"))]
    if op == "fan-duty":
        duty1 = _int(rest[0], MIN_DUTY, 255, "duty1")
        duty2 = _int(rest[1], MIN_DUTY, 255, "duty2")
        return [(FAN_SET, duty1 | duty2 << 8)]
    if op == "fan-auto":
        return [(FAN_AUTO, 0x0F)]
    if op == "fan-read":
        return [(cmd, 0) for cmd in FAN_READS]
    if op == "charge-set":
        stop = _int(rest[0], 40, 100, "stop")
        start = _int(rest[1], 40, 100, "start")
        if start >= stop:
            raise UsageError("start must be below stop")
        return [(CHARGE_SET, 0x06000000 | stop << 8 | start), (CHARGE_SET, 0x05000001)]
    if op == "charge-off":
        return [(CHARGE_SET, 0x05000000)]
    if op == "charge-get":
        return [(CHARGE_GET, 0)]
    code = _int(rest[0], 0, 255, "profile")
    if code not in PROFILES:
        raise UsageError(f"profile must be one of {PROFILES}, got {code}")
    return [(OPT, 0x01000000 | code)]


def format_call(cmd, arg):
    return f"{METHOD} 0 {cmd:#x} b{arg.to_bytes(4, 'little').hex()}"


def check_reply(raw):
    reply = raw.strip("\x00\n ")
    if not reply or reply.startswith("Error") or reply == "not called":
        raise RuntimeError(reply or "empty reply from acpi_call")
    return reply


def call_acpi(line):
    with open(ACPI_CALL, "w") as f:
        f.write(line)
    with open(ACPI_CALL) as f:
        return check_reply(f.read())


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        calls = encode(args)
    except UsageError as exc:
        print(f"vaio-wmi-helper: {exc}", file=sys.stderr)
        return 2

    fd = None
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        replies = [call_acpi(format_call(cmd, arg)) for cmd, arg in calls]
    except (OSError, RuntimeError) as exc:
        print(f"vaio-wmi-helper: {exc}", file=sys.stderr)
        return 1
    finally:
        if fd is not None:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    if args[0] == "fan-read":
        try:
            output = {f"{cmd:#x}": int(reply, 16) for (cmd, _), reply in zip(calls, replies)}
            print(json.dumps(output))
        except ValueError as exc:
            print(f"vaio-wmi-helper: unexpected reply format: {exc}", file=sys.stderr)
            return 1
    else:
        print(replies[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
