import json

from vaio_center.backend import status


def test_round_trip(tmp_path):
    path = tmp_path / "vaio-center" / "status.json"
    status.write({"mode": "quiet", "forced": False, "target": 25}, path)
    data = status.read(path)
    assert data["mode"] == "quiet"
    assert data["target"] == 25


def test_missing_garbled_or_stale_is_none(tmp_path):
    path = tmp_path / "status.json"
    assert status.read(path) is None
    path.write_text("{bad")
    assert status.read(path) is None
    path.write_text(json.dumps({"mode": "normal", "updated": 100.0}))
    assert status.read(path, now=100.0 + status.STALE_S + 1) is None
    assert status.read(path, now=105.0)["mode"] == "normal"


def test_path_uses_xdg_runtime_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    assert status.status_path() == tmp_path / "vaio-center" / "status.json"
