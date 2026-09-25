import pytest

import vaio_wmi_helper as helper


class Recorder:
    """Stands in for a backend module: records every call, returns a fixed error."""

    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def __getattr__(self, name):
        def method(*args):
            self.calls.append((name, *args))
            return self.error

        return method


@pytest.fixture
def recorder():
    return Recorder


@pytest.fixture(autouse=True)
def mock_lock_file(tmp_path, monkeypatch):
    """Monkeypatch LOCK_FILE to use a temp path for all tests."""
    monkeypatch.setattr(helper, "LOCK_FILE", str(tmp_path / "lock"))
