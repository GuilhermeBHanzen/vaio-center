import json

import pytest

import vaio_wmi_helper as helper


@pytest.mark.parametrize(
    "args, calls",
    [
        (["kbd-color", "0xFF0000"], [(0x67, 0xF000FF00)]),
        (["kbd-color", "0x0000FF"], [(0x67, 0xF0FF0000)]),
        (["kbd-color", "65280"], [(0x67, 0xF00000FF)]),
        (["events-on"], [(0x46, 0)]),
        (["event-get"], [(0x01, 0)]),
        (["kbd-brightness", "128"], [(0x67, 0xF4000080)]),
        (["fan-duty", "64", "255"], [(0x68, 0xFF40)]),
        (["fan-auto"], [(0x69, 0x0F)]),
        (["fan-read"], [(0x6F, 0), (0x70, 0)]),
        (["charge-set", "80", "75"], [(0x76, 0x0600504B), (0x76, 0x05000001)]),
        (["charge-off"], [(0x76, 0x05000000)]),
        (["charge-get"], [(0x77, 0)]),
        (["profile", "5"], [(0x79, 0x01000005)]),
    ],
)
def test_encode(args, calls):
    assert helper.encode(args) == calls


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["rm", "-rf", "/"],
        ["\\_SB.WMI.WMBB", "0", "0x67"],
        ["kbd-color", "0", "0xFF0000"],
        ["kbd-color", "0x1000000"],
        ["kbd-color"],
        ["events-on", "1"],
        ["event-get", "x"],
        ["kbd-brightness", "256"],
        ["fan-duty", "10", "200"],
        ["fan-duty", "100", "256"],
        ["fan-auto", "1"],
        ["charge-set", "80", "80"],
        ["charge-set", "30", "20"],
        ["charge-set", "101", "50"],
        ["profile", "3"],
        ["profile", "abc"],
    ],
)
def test_encode_rejects_bad_input(args):
    with pytest.raises(helper.UsageError):
        helper.encode(args)


def test_format_call_packs_little_endian_buffer():
    assert helper.format_call(0x67, 0xF3FF0000) == "\\_SB.WMI.WMBB 0 0x67 b0000fff3"


def test_check_reply_strips_nul_and_newline():
    assert helper.check_reply("0x76\x00\n") == "0x76"


@pytest.mark.parametrize("raw", ["Error: AE_NOT_FOUND", "not called", "\x00", ""])
def test_check_reply_rejects_errors(raw):
    with pytest.raises(RuntimeError):
        helper.check_reply(raw)


def test_main_sends_every_call_and_prints_the_last_reply(monkeypatch, capsys):
    sent = []

    def fake_call(line):
        sent.append(line)
        return "0x76"

    monkeypatch.setattr(helper, "call_acpi", fake_call)
    assert helper.main(["charge-set", "80", "75"]) == 0
    assert sent == [
        "\\_SB.WMI.WMBB 0 0x76 b4b500006",
        "\\_SB.WMI.WMBB 0 0x76 b01000005",
    ]
    assert capsys.readouterr().out == "0x76\n"


def test_main_fan_read_prints_json(monkeypatch, capsys):
    replies = {"0x6f": "0x2b2b51", "0x70": "0x3ae"}
    monkeypatch.setattr(helper, "call_acpi", lambda line: replies[line.split()[2]])
    assert helper.main(["fan-read"]) == 0
    assert json.loads(capsys.readouterr().out) == {"0x6f": 0x2B2B51, "0x70": 0x3AE}


def test_main_usage_error_exits_2(capsys):
    assert helper.main(["bogus"]) == 2
    assert "unknown sub-command" in capsys.readouterr().err


def test_main_acpi_failure_exits_1(monkeypatch, capsys):
    def fail(line):
        raise RuntimeError("Error: AE_NOT_FOUND")

    monkeypatch.setattr(helper, "call_acpi", fail)
    assert helper.main(["charge-get"]) == 1
    assert "AE_NOT_FOUND" in capsys.readouterr().err


def test_helper_has_isolated_absolute_python_shebang():
    with open(helper.__file__) as f:
        assert f.readline().strip() == "#!/usr/bin/python3 -I"


def test_main_creates_lock_file(monkeypatch, tmp_path):
    """Verify lock file is created after successful main() call."""
    lock_path = tmp_path / "lock"
    monkeypatch.setattr(helper, "LOCK_FILE", str(lock_path))
    monkeypatch.setattr(helper, "call_acpi", lambda line: "0x76")

    assert helper.main(["charge-get"]) == 0
    assert lock_path.exists()


def test_main_fan_read_rejects_non_hex_reply(monkeypatch, capsys):
    """Verify fan-read with non-hex reply returns 1 and error message."""
    def fake_call(line):
        return "garbage"

    monkeypatch.setattr(helper, "call_acpi", fake_call)
    assert helper.main(["fan-read"]) == 1
    stderr = capsys.readouterr().err
    assert "vaio-wmi-helper:" in stderr
