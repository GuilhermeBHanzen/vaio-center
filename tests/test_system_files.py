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
