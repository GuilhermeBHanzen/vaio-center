#!/bin/sh
# Installs the root-owned parts of vaio-center. Run: sudo ./install-root.sh
set -eu
here=$(dirname "$(readlink -f "$0")")
if [ "$(id -u)" -ne 0 ]; then
    echo "run with sudo" >&2
    exit 1
fi
install -D -o root -g root -m 0755 "$here/helper/vaio_wmi_helper.py" /usr/local/libexec/vaio-wmi-helper
install -D -o root -g root -m 0644 "$here/system/org.local.vaio-center.policy" /usr/share/polkit-1/actions/org.local.vaio-center.policy
install -D -o root -g root -m 0644 "$here/system/acpi_call.conf" /etc/modules-load.d/acpi_call.conf
modprobe acpi_call
echo "root parts installed"
