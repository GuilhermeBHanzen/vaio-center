# vaio-center

A Linux replacement for the Windows **VAIO Control Center** on the **VAIO FH15** (Positivo "Bahia", board `VJFH52-RPL`, Clevo-based firmware). It covers keyboard RGB and the Fn backlight keys, fan profiles, the battery charge limit and performance profiles, as a GTK4/libadwaita app plus a small user daemon.

> The UI is in Brazilian Portuguese (pt-BR). Tested only on the VAIO FH15 (VJFH52). Other Clevo-based laptops may expose the same WMI method, but **commands write to the embedded controller (EC): use at your own risk.**

## Features

| Tab | What it does |
|---|---|
| **Teclado** | Sets the keyboard RGB colour (single zone) and brightness. Makes the Fn backlight keys (down/up/toggle) work through the daemon. |
| **Ventoinhas** | Fan profiles: quiet, normal, aggressive (40% → 100% by 68 °C, with hysteresis), manual duty and max. Shows live RPM and temperature, and falls back to EC auto at 90 °C. |
| **Desempenho** | Battery charge limit (presets 60/55 · 80/75 · 100, custom, or "defined in BIOS" to leave the firmware's limit untouched) and EC performance profiles. |
| **Bateria / Energia (TLP) / Tela / GPU** | Battery health and status, TLP power mode, screen brightness, NVIDIA hybrid GPU status. |

Settings are restored at login. The user daemon retries with backoff, because polkit refuses before the session is active.

## How it works

Everything goes through one ACPI WMI method, `\_SB.WMI.WMBB` (GUID `ABBC0F6D-8EA1-11D1-00A0-C90629100000`), called via the [`acpi_call`](https://github.com/nix-community/acpi_call) kernel module:

```
GTK app / daemon ──pkexec──► /usr/local/libexec/vaio-wmi-helper ──► /proc/acpi/call ──► \_SB.WMI.WMBB
   (user)          (polkit)       (root, command whitelist)
```

The root helper only accepts a fixed whitelist of commands with validated arguments. A polkit action lets the active local session run it without a password.

| WMBB cmd | Purpose |
|---|---|
| `0x67` | Keyboard colour (`0xF0000000 \| B<<16 \| R<<8 \| G`, note the B-R-G order) and brightness (`0xF4000000 \| level`) |
| `0x46` / `0x01` | Enable hotkey events / read the last event code (`0x82` down, `0x81` up, `0x9F` toggle) |
| `0x68` / `0x69` | Set fan duty bytes / return fans to EC auto |
| `0x6F` / `0x70` | Read fan duty + temperature / tach periods (RPM = 2156220 / period) |
| `0x76` / `0x77` | Set / read the charge limit (stop %, start %, enabled) |
| `0x79` | Select an EC performance profile |

These were found by reverse-engineering the ACPI tables (DSDT/SSDT) and the Windows app.

## Requirements

- Arch Linux (or similar), Python ≥ 3.12, PyGObject with GTK 4 and libadwaita
- `acpi_call` (DKMS), `acpid`, polkit, a systemd user session
- Optional: TLP (power tab), Waybar (tray icon)

## Install

```sh
git clone https://github.com/GuilhermeBHanzen/vaio-center
cd vaio-center
sudo ./install-root.sh   # root helper, polkit policy, acpi_call module autoload, acpid
./install.sh             # app + launcher + desktop entry + waybar icon + user daemon
```

## Development

```sh
python3 -m pytest -q
```

The backend, fan policy, daemon logic and the root helper's argument whitelist are unit-tested without touching hardware.

## License

[MIT](LICENSE)
