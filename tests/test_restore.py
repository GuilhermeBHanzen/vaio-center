import copy

from vaio_center import __main__ as entry
from vaio_center import restore
from vaio_center.backend import state


class Level:
    def load(self):
        return 204


def test_restore_defaults(recorder):
    wmi = recorder()
    assert restore.restore(copy.deepcopy(state.DEFAULTS), wmi, Level()) == []
    assert wmi.calls == [
        ("set_fan_auto",),
        ("set_keyboard_color", 0x0000C8),
        ("set_keyboard_brightness", 204),
        ("disable_charge_limit",),
    ]


def test_restore_profile_and_charge_limit(recorder):
    data = copy.deepcopy(state.DEFAULTS)
    data["profile"] = 5
    data["charge"] = {"enabled": True, "stop": 80, "start": 75}
    wmi = recorder()
    restore.restore(data, wmi, Level())
    assert ("set_profile", 5) in wmi.calls
    assert wmi.calls[-1] == ("set_charge_limit", 80, 75)


def test_restore_collects_errors(recorder):
    errors = restore.restore(copy.deepcopy(state.DEFAULTS), recorder(error="boom"), Level())
    assert errors == ["boom"] * 4


def test_restore_flag_runs_without_gui(monkeypatch, capsys):
    monkeypatch.setattr(entry.state, "load", lambda: {"marker": True})
    monkeypatch.setattr(entry.restore, "restore", lambda data: ["boom"] if data == {"marker": True} else [])
    assert entry.main(["vaio-center", "--restore"]) == 1
    assert "boom" in capsys.readouterr().err


def test_restore_value_error_does_not_abort_the_rest(recorder):
    class BadProfile(recorder):
        def set_profile(self, code):
            raise ValueError(f"bad profile {code}")

    data = copy.deepcopy(state.DEFAULTS)
    data["profile"] = 3
    wmi = BadProfile()
    assert restore.restore(data, wmi, Level()) == ["bad profile 3"]
    assert wmi.calls[-1] == ("disable_charge_limit",)
