import json

from vaio_center.backend import state


def test_missing_file_returns_independent_defaults(tmp_path):
    loaded = state.load(tmp_path / "state.json")
    assert loaded == state.DEFAULTS
    loaded["keyboard"]["zones"][0] = 1
    assert state.DEFAULTS["keyboard"]["zones"][0] == 0x0000C8


def test_round_trip(tmp_path):
    path = tmp_path / "nested" / "state.json"
    data = state.load(path)
    data["profile"] = 5
    data["charge"] = {"enabled": True, "stop": 80, "start": 75}
    state.save(data, path)
    assert state.load(path) == data
    assert not path.with_suffix(".tmp").exists()


def test_corrupt_file_returns_defaults(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not json")
    assert state.load(path) == state.DEFAULTS


def test_non_object_json_returns_defaults(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("[1, 2]")
    assert state.load(path) == state.DEFAULTS


def test_partial_file_is_merged_with_defaults_and_unknown_keys_dropped(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"charge": {"stop": 90}, "bogus": 1}))
    loaded = state.load(path)
    assert loaded["charge"] == {"enabled": False, "stop": 90, "start": 75}
    assert loaded["keyboard"] == state.DEFAULTS["keyboard"]
    assert "bogus" not in loaded


def test_state_path_honours_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert state.state_path() == tmp_path / "vaio-center" / "state.json"
