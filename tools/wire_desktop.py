"""Idempotently hooks vaio-center into the user's waybar and Hyprland config.

Anchors on the existing custom/tlpinfo entries, the same places the TLP module
was wired into, so HyDE layout regeneration keeps both together.
"""
import sys
from pathlib import Path

AUTOSTART_MARKER = "-- vaio-center: re-apply"


def add_after_tlp(text, entry):
    if entry in text:
        return text
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if "tlpinfo" in line and line.rstrip().endswith(","):
            indent = line[: len(line) - len(line.lstrip())]
            lines.insert(index + 1, f"{indent}{entry},\n")
            return "".join(lines)
    raise ValueError("no tlpinfo entry to anchor on")


def add_autostart(text, launcher):
    if AUTOSTART_MARKER in text:
        return text
    block = (
        f"\n{AUTOSTART_MARKER} keyboard colors, EC profile and charge limit after login\n"
        'hl.on("hyprland.start", function()\n'
        f'\thl.exec_cmd("{launcher} --restore")\n'
        "end)\n"
    )
    return text.rstrip("\n") + "\n" + block


def main(argv):
    launcher = argv[1]
    home = Path.home()
    module = f'"{home}/.local/share/waybar/modules/custom-vaio-center.jsonc"'
    edits = [
        (home / ".config/waybar/includes/includes.json", lambda t: add_after_tlp(t, module)),
        (home / ".config/waybar/config.jsonc", lambda t: add_after_tlp(t, '"custom/vaio-center"')),
        (home / ".local/share/waybar/layouts/hyprdots/17.jsonc", lambda t: add_after_tlp(t, '"custom/vaio-center"')),
        (home / ".config/hypr/hyprland.lua", lambda t: add_autostart(t, launcher)),
    ]
    for path, edit in edits:
        if not path.exists():
            print(f"skip (missing): {path}")
            continue
        text = path.read_text()
        try:
            new = edit(text)
        except ValueError:
            print(f"skip (no anchor): {path}")
            continue
        if new != text:
            path.write_text(new)
            print(f"updated: {path}")
        else:
            print(f"unchanged: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
