import pytest

pytest.importorskip("gi")

from vaio_center.tabs import performance  # noqa: E402


def test_preset_index():
    names = [p[0] for p in performance.PRESETS]
    assert names == ["Máxima vida útil", "Equilibrado", "Carga completa"]
    assert performance.preset_index(True, 60, 55) == 0
    assert performance.preset_index(True, 80, 75) == 1
    assert performance.preset_index(False, 95, 75) == 2
    assert performance.preset_index(True, 95, 75) == 3
