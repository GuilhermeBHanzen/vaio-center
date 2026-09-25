from vaio_center.backend import brightness


def test_parse_machine_output():
    assert brightness.parse_machine("intel_backlight,backlight,24000,50%,48000\n") == {
        "device": "intel_backlight",
        "percent": 50,
    }


def test_get_percent(monkeypatch):
    monkeypatch.setattr(brightness.proc, "run", lambda cmd, timeout=10: ("intel_backlight,backlight,24000,50%,48000\n", None))
    assert brightness.get_percent() == 50


def test_get_percent_error(monkeypatch):
    monkeypatch.setattr(brightness.proc, "run", lambda cmd, timeout=10: (None, "boom"))
    assert brightness.get_percent() is None


def test_set_percent_clamps(monkeypatch):
    calls = []
    monkeypatch.setattr(brightness.proc, "run", lambda cmd, timeout=10: (calls.append(cmd), ("", None))[1])
    assert brightness.set_percent(0) is None
    brightness.set_percent(150)
    assert calls == [["brightnessctl", "-q", "set", "1%"], ["brightnessctl", "-q", "set", "100%"]]
