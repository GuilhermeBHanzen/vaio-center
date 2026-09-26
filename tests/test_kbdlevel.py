from vaio_center.backend import kbdlevel


def test_missing_file_is_default(tmp_path):
    assert kbdlevel.load(tmp_path / "kbd-brightness") == kbdlevel.DEFAULT


def test_round_trip_and_clamp(tmp_path):
    path = tmp_path / "sub" / "kbd-brightness"
    kbdlevel.save(102, path)
    assert kbdlevel.load(path) == 102
    path.write_text("999\n")
    assert kbdlevel.load(path) == 255
    path.write_text("-4\n")
    assert kbdlevel.load(path) == 0


def test_garbage_is_default(tmp_path):
    path = tmp_path / "kbd-brightness"
    path.write_text("abc")
    assert kbdlevel.load(path) == kbdlevel.DEFAULT


def test_path_honours_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert kbdlevel.level_path() == tmp_path / "vaio-center" / "kbd-brightness"
