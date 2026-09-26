#!/bin/sh
# Installs vaio-center for the current user. Root parts: sudo ./install-root.sh
set -eu
here=$(dirname "$(readlink -f "$0")")
lib="$HOME/.local/lib/vaio-center"
bin="$HOME/.local/bin/vaio-center"

mkdir -p "$lib" "$HOME/.local/bin" "$HOME/.local/share/applications" "$HOME/.local/share/waybar/modules"
rm -rf "$lib/vaio_center"
cp -r "$here/vaio_center" "$lib/vaio_center"
find "$lib" -name __pycache__ -type d -prune -exec rm -rf {} +
install -m 0755 "$here/data/vaio-center" "$bin"
sed "s|@BIN@|$bin|g" "$here/data/vaio-center.desktop.in" > "$HOME/.local/share/applications/vaio-center.desktop"
sed "s|@BIN@|$bin|g" "$here/data/custom-vaio-center.jsonc.in" > "$HOME/.local/share/waybar/modules/custom-vaio-center.jsonc"
python3 "$here/tools/wire_desktop.py" "$bin"
install -D -m 0644 "$here/data/vaio-center.service" "$HOME/.config/systemd/user/vaio-center.service"
systemctl --user daemon-reload
systemctl --user enable vaio-center.service
systemctl --user restart vaio-center.service
pkill -SIGUSR2 waybar || true
echo "vaio-center installed: app launcher, waybar laptop icon, or $bin"
