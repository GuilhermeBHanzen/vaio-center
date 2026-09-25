import pytest

from vaio_center.backend import proc, tlp

TLP_STAT = """\
--- TLP 1.10.2 --------------------------------------------

+++ TLP Status
tlp            = enabled, last run: 08:34:12 PM, 778 sec(s) ago
TLP profile    = performance/AC
Power source   = AC
"""


@pytest.fixture
def cache(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    return tmp_path / "hyde" / "tlp-mode"


def test_parse_profile():
    assert tlp.parse_profile(TLP_STAT) == "performance"
    assert tlp.parse_profile("nothing here") is None


def test_get_mode_prefers_the_waybar_cache_file(cache, monkeypatch):
    cache.parent.mkdir(parents=True)
    cache.write_text("balanced\n")
    monkeypatch.setattr(tlp.proc, "run", lambda cmd, timeout=10: pytest.fail("should not run"))
    assert tlp.get_mode() == "balanced"


def test_get_mode_falls_back_to_tlp_stat(cache, monkeypatch):
    monkeypatch.setattr(tlp.proc, "run", lambda cmd, timeout=10: (TLP_STAT, None))
    assert tlp.get_mode() == "performance"


def test_get_mode_ignores_garbage_in_cache(cache, monkeypatch):
    cache.parent.mkdir(parents=True)
    cache.write_text("turbo\n")
    monkeypatch.setattr(tlp.proc, "run", lambda cmd, timeout=10: (TLP_STAT, None))
    assert tlp.get_mode() == "performance"


def test_set_mode_success_writes_cache_and_signals_waybar(cache, monkeypatch):
    calls = []
    monkeypatch.setattr(tlp.proc, "run", lambda cmd, timeout=10: (calls.append(cmd), ("", None))[1])
    assert tlp.set_mode("power-saver") is None
    assert calls == [["pkexec", "tlp", "power-saver"], ["pkill", "-RTMIN+3", "waybar"]]
    assert cache.read_text() == "power-saver\n"


def test_set_mode_cancelled_leaves_cache_alone(cache, monkeypatch):
    monkeypatch.setattr(tlp.proc, "run", lambda cmd, timeout=10: (None, proc.CANCELLED))
    assert tlp.set_mode("balanced") == proc.CANCELLED
    assert not cache.exists()


def test_set_mode_rejects_unknown_mode():
    with pytest.raises(ValueError):
        tlp.set_mode("turbo")
