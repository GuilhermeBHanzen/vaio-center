import pytest

from vaio_center.backend import gpu

LINE = "NVIDIA GeForce RTX 3050 Laptop GPU, 42, 0, 5.66, 14, 4096, P8\n"


def test_parse_query():
    assert gpu.parse_query(LINE) == {
        "name": "NVIDIA GeForce RTX 3050 Laptop GPU",
        "temp_c": 42,
        "util_pct": 0,
        "power_w": 5.66,
        "mem_used_mib": 14,
        "mem_total_mib": 4096,
        "pstate": "P8",
    }


def test_parse_query_tolerates_not_available():
    assert gpu.parse_query("GPU, 42, 0, [N/A], 14, 4096, P8")["power_w"] is None


def test_runtime_status_reads_sysfs(tmp_path):
    path = tmp_path / "runtime_status"
    path.write_text("suspended\n")
    assert gpu.runtime_status(path) == "suspended"
    assert gpu.runtime_status(tmp_path / "missing") is None


def test_suspended_gpu_is_not_woken(monkeypatch):
    monkeypatch.setattr(gpu, "runtime_status", lambda path=gpu.PCI_RUNTIME: "suspended")
    monkeypatch.setattr(gpu.proc, "run", lambda cmd, timeout=10: pytest.fail("nvidia-smi would wake the dGPU"))
    assert gpu.get_status() == {"suspended": True}


def test_active_gpu_is_queried(monkeypatch):
    monkeypatch.setattr(gpu, "runtime_status", lambda path=gpu.PCI_RUNTIME: "active")
    monkeypatch.setattr(gpu.proc, "run", lambda cmd, timeout=10: (LINE, None))
    status = gpu.get_status()
    assert status["suspended"] is False
    assert status["temp_c"] == 42


def test_bad_output_is_an_error(monkeypatch):
    monkeypatch.setattr(gpu, "runtime_status", lambda path=gpu.PCI_RUNTIME: "active")
    monkeypatch.setattr(gpu.proc, "run", lambda cmd, timeout=10: ("garbage\n", None))
    assert "unexpected" in gpu.get_status()["error"]
