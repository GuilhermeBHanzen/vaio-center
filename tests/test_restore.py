import copy

from vaio_center import __main__ as entry
from vaio_center import restore
from vaio_center.backend import state


def test_restore_defaults(recorder):
    wmi = recorder()
    assert restore.restore(copy.deepcopy(state.DEFAULTS), wmi) == []
    assert wmi.calls == [
        ("set_zone_color", 0, 0x0000C8, 100),
        ("set_zone_color", 1, 0x0000C8, 100),
        ("set_zone_color", 2, 0x0000C8, 100),
        ("set_keyboard_brightness", 255),
        ("disable_charge_limit",),
    ]


def test_restore_profile_and_charge_limit(recorder):
    data = copy.deepcopy(state.DEFAULTS)
    data["profile"] = 5
    data["charge"] = {"enabled": True, "stop": 80, "start": 75}
    wmi = recorder()
    restore.restore(data, wmi)
    assert ("set_profile", 5) in wmi.calls
    assert wmi.calls[-1] == ("set_charge_limit", 80, 75)


def test_restore_collects_errors(recorder):
    errors = restore.restore(copy.deepcopy(state.DEFAULTS), recorder(error="boom"))
    assert errors == ["boom"] * 5


def test_restore_flag_runs_without_gui(monkeypatch, capsys):
    monkeypatch.setattr(entry.state, "load", lambda: {"marker": True})
    monkeypatch.setattr(entry.restore, "restore", lambda data: ["boom"] if data == {"marker": True} else [])
    assert entry.main(["vaio-center", "--restore"]) == 1
    assert "boom" in capsys.readouterr().err
