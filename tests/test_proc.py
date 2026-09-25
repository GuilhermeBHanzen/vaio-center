import subprocess

from vaio_center.backend import proc


def fake_run(returncode=0, stdout="", stderr=""):
    def run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)

    return run


def test_success_returns_stdout(monkeypatch):
    monkeypatch.setattr(proc.subprocess, "run", fake_run(0, "hello\n"))
    assert proc.run(["echo"]) == ("hello\n", None)


def test_failure_returns_stripped_stderr(monkeypatch):
    monkeypatch.setattr(proc.subprocess, "run", fake_run(1, "", "boom\n"))
    assert proc.run(["tool"]) == (None, "boom")


def test_failure_without_stderr_names_the_exit_code(monkeypatch):
    monkeypatch.setattr(proc.subprocess, "run", fake_run(3))
    assert proc.run(["tool"]) == (None, "tool exited with 3")


def test_dismissed_pkexec_is_cancelled(monkeypatch):
    monkeypatch.setattr(proc.subprocess, "run", fake_run(126))
    assert proc.run(["pkexec", "tlp", "balanced"]) == (None, proc.CANCELLED)


def test_exit_126_from_other_tools_is_a_plain_error(monkeypatch):
    monkeypatch.setattr(proc.subprocess, "run", fake_run(126))
    assert proc.run(["tool"]) == (None, "tool exited with 126")


def test_missing_binary_is_an_error(monkeypatch):
    def boom(cmd, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", cmd[0])

    monkeypatch.setattr(proc.subprocess, "run", boom)
    out, err = proc.run(["nope"])
    assert out is None
    assert "No such file" in err


def test_timeout_is_an_error(monkeypatch):
    def slow(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 10)

    monkeypatch.setattr(proc.subprocess, "run", slow)
    out, err = proc.run(["slow"])
    assert out is None
    assert "timed out" in err
