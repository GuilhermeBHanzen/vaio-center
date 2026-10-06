import pytest

pytest.importorskip("gi")

from vaio_center.tabs import performance  # noqa: E402


def test_preset_index():
    names = [p[0] for p in performance.PRESETS]
    assert names == ["Máxima vida útil", "Equilibrado", "Carga completa"]
    assert performance.BIOS_LABEL == "Definido na BIOS"
    assert performance.preset_index("bios", True, 95, 40) == 0
    assert performance.preset_index("app", True, 60, 55) == 1
    assert performance.preset_index("app", True, 80, 75) == 2
    assert performance.preset_index("app", False, 80, 75) == 3
    assert performance.preset_index("app", True, 95, 75) == 4
