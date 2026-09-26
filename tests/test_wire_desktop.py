import pytest

import wire_desktop

CONFIG = """\
        "modules-right": [
            "battery",
            "custom/tlpinfo",
            "cpu"
        ]
"""

INCLUDES = """\
    "include": [
        "/home/u/.local/share/waybar/modules/custom-tlpinfo.jsonc",
        "/home/u/.local/share/waybar/modules/image#wallpaper.jsonc"
    ],
"""


def test_adds_module_after_tlp_with_same_indent():
    out = wire_desktop.add_after_tlp(CONFIG, '"custom/vaio-center"')
    assert '            "custom/tlpinfo",\n            "custom/vaio-center",\n            "cpu"' in out


def test_adds_include_after_tlp_include():
    entry = '"/home/u/.local/share/waybar/modules/custom-vaio-center.jsonc"'
    out = wire_desktop.add_after_tlp(INCLUDES, entry)
    assert f"custom-tlpinfo.jsonc\",\n        {entry},\n" in out


def test_add_after_tlp_is_idempotent():
    once = wire_desktop.add_after_tlp(CONFIG, '"custom/vaio-center"')
    assert wire_desktop.add_after_tlp(once, '"custom/vaio-center"') == once


def test_add_after_tlp_needs_an_anchor():
    with pytest.raises(ValueError):
        wire_desktop.add_after_tlp('"cpu",\n', '"custom/vaio-center"')


V1_HOOK = (
    "-- user config\n\n"
    "-- vaio-center: re-apply keyboard colors, EC profile and charge limit after login\n"
    'hl.on("hyprland.start", function()\n'
    '\thl.exec_cmd("/home/u/.local/bin/vaio-center --restore")\n'
    "end)\n"
)


def test_remove_autostart_drops_v1_hook():
    assert wire_desktop.remove_autostart(V1_HOOK) == "-- user config\n"
    assert wire_desktop.remove_autostart("-- user config\n") == "-- user config\n"


def test_main_edits_existing_files_and_skips_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(wire_desktop.Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".config/waybar/includes").mkdir(parents=True)
    (tmp_path / ".config/waybar/includes/includes.json").write_text(INCLUDES)
    (tmp_path / ".config/waybar/config.jsonc").write_text(CONFIG)
    (tmp_path / ".config/hypr").mkdir(parents=True)
    (tmp_path / ".config/hypr/hyprland.lua").write_text(V1_HOOK)
    assert wire_desktop.main(["wire_desktop.py", str(tmp_path / ".local/bin/vaio-center")]) == 0
    assert "custom/vaio-center" in (tmp_path / ".config/waybar/config.jsonc").read_text()
    assert "custom-vaio-center.jsonc" in (tmp_path / ".config/waybar/includes/includes.json").read_text()
    assert "--restore" not in (tmp_path / ".config/hypr/hyprland.lua").read_text()
    assert "skip" in capsys.readouterr().out  # the layout file does not exist in tmp


def test_main_skips_a_file_without_anchor_and_continues(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(wire_desktop.Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".config/waybar/includes").mkdir(parents=True)
    includes = tmp_path / ".config/waybar/includes/includes.json"
    includes.write_text('"include": [\n    "/x/image.jsonc"\n],\n')
    (tmp_path / ".config/waybar/config.jsonc").write_text(CONFIG)
    assert wire_desktop.main(["wire_desktop.py", "/home/u/.local/bin/vaio-center"]) == 0
    assert f"skip (no anchor): {includes}" in capsys.readouterr().out
    assert "custom/vaio-center" in (tmp_path / ".config/waybar/config.jsonc").read_text()
