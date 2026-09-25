from vaio_center.backend import battery

UPOWER_FULL = """\
  native-path:          BAT0
  vendor:               SCUD(FUJIAN)Electronics CO.,Ltd
  model:                NP50BAT-4-54
  serial:               0-00-TEST-00000
  updated:              Wed 23 Sep 2026 08:46:42 PM -03 (19 seconds ago)
  battery
    present:             yes
    state:               fully-charged
    energy:              40.04 Wh
    energy-full:         40.04 Wh
    energy-full-design:  52.514 Wh
    energy-rate:         0 W
    percentage:          100%
    capacity:            76.2463%
  History (voltage):
    1790207112	16.801	fully-charged
"""

UPOWER_DISCHARGING = """\
  battery
    state:               discharging
    energy-rate:         12.5 W
    percentage:          64%
    time to empty:       2.3 hours
"""


def test_parse_full_battery():
    assert battery.parse_upower(UPOWER_FULL) == {
        "state": "fully-charged",
        "energy_full": 40.04,
        "energy_full_design": 52.514,
        "rate": 0.0,
        "percentage": 100.0,
        "health": 76.2463,
    }


def test_parse_discharging_keeps_time_text():
    info = battery.parse_upower(UPOWER_DISCHARGING)
    assert info["time_to_empty"] == "2.3 hours"
    assert info["rate"] == 12.5


def test_get_status_queries_bat0(monkeypatch):
    seen = []
    monkeypatch.setattr(battery.proc, "run", lambda cmd, timeout=10: (seen.append(cmd), (UPOWER_FULL, None))[1])
    assert battery.get_status()["percentage"] == 100.0
    assert seen == [["upower", "-i", battery.DEVICE]]


def test_get_status_error(monkeypatch):
    monkeypatch.setattr(battery.proc, "run", lambda cmd, timeout=10: (None, "no upower"))
    assert battery.get_status() == {"error": "no upower"}
