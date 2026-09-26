import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELPER_PATH = "/usr/local/libexec/vaio-wmi-helper"


def test_policy_targets_the_helper_and_skips_prompt_only_for_active_sessions():
    action = ET.parse(ROOT / "system" / "org.local.vaio-center.policy").find("action")
    assert action.get("id") == "org.local.vaio-center.wmi"
    annotate = action.find("annotate[@key='org.freedesktop.policykit.exec.path']")
    assert annotate.text == HELPER_PATH
    assert action.findtext("defaults/allow_active") == "yes"
    assert action.findtext("defaults/allow_inactive") == "auth_admin"
    assert action.findtext("defaults/allow_any") == "auth_admin"


def test_root_installer_installs_helper_policy_and_module_config():
    script = (ROOT / "install-root.sh").read_text()
    assert HELPER_PATH in script
    assert "/usr/share/polkit-1/actions/org.local.vaio-center.policy" in script
    assert "/etc/modules-load.d/acpi_call.conf" in script


def test_modules_load_file_names_acpi_call():
    assert (ROOT / "system" / "acpi_call.conf").read_text().strip() == "acpi_call"


def test_waybar_button_launches_through_uwsm():
    # A plain child of waybar dies on every waybar reload; uwsm gives it its own unit.
    template = (ROOT / "data" / "custom-vaio-center.jsonc.in").read_text()
    assert '"on-click": "uwsm app -- @BIN@"' in template


def test_user_unit_runs_daemon_and_returns_fans_to_auto():
    unit = (ROOT / "data" / "vaio-center.service").read_text()
    assert "ExecStart=%h/.local/bin/vaio-center --daemon" in unit
    assert "ExecStopPost=%h/.local/bin/vaio-center --fan-auto" in unit
    assert "Restart=on-failure" in unit


def test_user_unit_has_start_limit_and_stop_timeout():
    unit = (ROOT / "data" / "vaio-center.service").read_text()
    assert "StartLimitIntervalSec=120" in unit
    assert "StartLimitBurst=5" in unit
    assert "TimeoutStopSec=20" in unit


def test_user_installer_guards_systemctl_user_calls():
    script = (ROOT / "install.sh").read_text()
    assert (
        "systemctl --user daemon-reload && systemctl --user enable vaio-center.service "
        '&& systemctl --user restart vaio-center.service || echo "warn: user systemd not '
        'reachable; run later: systemctl --user enable --now vaio-center" >&2'
    ) in script


def test_root_installer_enables_acpid():
    assert "systemctl enable --now acpid" in (ROOT / "install-root.sh").read_text()
