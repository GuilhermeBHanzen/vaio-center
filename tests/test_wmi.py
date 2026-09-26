import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import vaio_wmi_helper
from vaio_center.backend import proc, wmi

ROOT = Path(__file__).resolve().parent.parent


class FakeHelper:
    def __init__(self):
        self.calls = []
        self.replies = {}

    def __call__(self, cmd, timeout=10):
        assert cmd[:2] == ["pkexec", wmi.HELPER]
        self.calls.append(cmd[2:])
        return self.replies.get(cmd[2], ("0x0\n", None))


@pytest.fixture
def helper(monkeypatch):
    fake = FakeHelper()
    monkeypatch.setattr(wmi.proc, "run", fake)
    return fake


def test_byte_from_percent():
    assert wmi.byte_from_percent(100) == 255
    assert wmi.byte_from_percent(30) == 77
    assert wmi.byte_from_percent(0) == 0


def test_set_keyboard_color(helper):
    assert wmi.set_keyboard_color(0xFF0000) is None
    assert helper.calls == [["kbd-color", str(0xFF0000)]]


def test_events_on(helper):
    assert wmi.events_on() is None
    assert helper.calls == [["events-on"]]


def test_get_event(helper):
    helper.replies["event-get"] = ("0x82\n", None)
    assert wmi.get_event() == 0x82


def test_get_event_error_or_garbage_is_none(helper):
    helper.replies["event-get"] = (None, "boom")
    assert wmi.get_event() is None
    helper.replies["event-get"] = ("nonsense\n", None)
    assert wmi.get_event() is None


def test_setters_build_expected_argv(helper):
    wmi.set_keyboard_brightness(128)
    wmi.set_fan_duty(77, 77)
    wmi.set_fan_auto()
    wmi.set_charge_limit(80, 75)
    wmi.disable_charge_limit()
    wmi.set_profile(5)
    assert helper.calls == [
        ["kbd-brightness", "128"],
        ["fan-duty", "77", "77"],
        ["fan-auto"],
        ["charge-set", "80", "75"],
        ["charge-off"],
        ["profile", "5"],
    ]


def test_setter_passes_cancelled_through(helper):
    helper.replies["fan-auto"] = (None, proc.CANCELLED)
    assert wmi.set_fan_auto() == proc.CANCELLED


def test_set_profile_rejects_unknown_code(helper):
    with pytest.raises(ValueError):
        wmi.set_profile(3)
    assert helper.calls == []


def test_decode_charge():
    assert wmi.decode_charge(0x504B01) == {"enabled": True, "start": 75, "stop": 80}
    assert wmi.decode_charge(0x645F00) == {"enabled": False, "start": 95, "stop": 100}


def test_get_charge_limit(helper):
    helper.replies["charge-get"] = ("0x504b01\n", None)
    assert wmi.get_charge_limit() == {"enabled": True, "start": 75, "stop": 80}


def test_get_charge_limit_error(helper):
    helper.replies["charge-get"] = (None, "boom")
    assert wmi.get_charge_limit() == {"error": "boom"}


def test_get_charge_limit_garbage(helper):
    helper.replies["charge-get"] = ("nonsense\n", None)
    assert "unexpected" in wmi.get_charge_limit()["error"]


def test_rpm():
    assert wmi.rpm(942) == 2289
    assert wmi.rpm(0) == 0


def test_decode_fans_matches_live_reading():
    assert wmi.decode_fans(0x2B2B51, 0x3AE) == {
        "fan1_duty_pct": 32,
        "ec_temp_c": 43,
        "fan1_rpm": 2289,
        "fan2_rpm": 0,
    }


def test_read_fans(helper):
    both_942 = 942 << 16 | 942  # == 61735854
    helper.replies["fan-read"] = (f'{{"0x6f": 2829137, "0x70": {both_942}}}\n', None)
    fans = wmi.read_fans()
    assert fans["fan1_rpm"] == 2289
    assert fans["fan2_rpm"] == 2289


def test_read_fans_bad_json(helper):
    helper.replies["fan-read"] = ("{}\n", None)
    assert "unexpected" in wmi.read_fans()["error"]


def test_profile_labels_are_accepted_by_helper():
    assert set(wmi.PROFILE_LABELS) <= set(vaio_wmi_helper.PROFILES)


def test_helper_path_matches_polkit_policy():
    action = ET.parse(ROOT / "system" / "org.local.vaio-center.policy").find("action")
    annotate = action.find("annotate[@key='org.freedesktop.policykit.exec.path']")
    assert annotate.text == wmi.HELPER
