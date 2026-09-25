import pytest

pytest.importorskip("gi")

from gi.repository import GLib  # noqa: E402

from vaio_center import ui  # noqa: E402


def test_rgba_round_trip():
    for rgb in (0x000000, 0xFF0000, 0x00FF00, 0x0000C8, 0x123456, 0xFFFFFF):
        assert ui.int_from_rgba(ui.rgba_from_int(rgb)) == rgb


def test_debouncer_fires_once_with_last_args():
    got = []
    loop = GLib.MainLoop()

    def callback(value):
        got.append(value)
        loop.quit()

    debounced = ui.Debouncer(10, callback)
    debounced(1)
    debounced(2)
    debounced(3)
    GLib.timeout_add(1000, loop.quit)
    loop.run()
    assert got == [3]
