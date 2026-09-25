"""CPU package temperature. hwmon numbering changes between boots, so look it up by name."""
from pathlib import Path

HWMON = "/sys/class/hwmon"


def cpu_temp_c(root=HWMON):
    for hwmon in sorted(Path(root).glob("hwmon*")):
        try:
            if (hwmon / "name").read_text().strip() != "coretemp":
                continue
            return int((hwmon / "temp1_input").read_text()) / 1000
        except (OSError, ValueError):
            return None
    return None
