from vaio_center.backend import sensors


def make_hwmon(root, index, name, temp=None):
    hw = root / f"hwmon{index}"
    hw.mkdir()
    (hw / "name").write_text(name + "\n")
    if temp is not None:
        (hw / "temp1_input").write_text(f"{temp}\n")


def test_reads_coretemp_package_temperature(tmp_path):
    make_hwmon(tmp_path, 1, "acpitz", 30000)
    make_hwmon(tmp_path, 5, "coretemp", 44000)
    assert sensors.cpu_temp_c(tmp_path) == 44.0


def test_no_coretemp_returns_none(tmp_path):
    make_hwmon(tmp_path, 1, "acpitz", 30000)
    assert sensors.cpu_temp_c(tmp_path) is None


def test_unreadable_value_returns_none(tmp_path):
    make_hwmon(tmp_path, 5, "coretemp")
    assert sensors.cpu_temp_c(tmp_path) is None
