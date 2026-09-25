import pytest


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
