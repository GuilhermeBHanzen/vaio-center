"""Single place where the app runs external commands."""
import subprocess

CANCELLED = "cancelled"
PKEXEC_DISMISSED = 126
PKEXEC_NOT_AUTHORIZED = 127
NOT_AUTHORIZED = "Sem autorização do polkit ou helper ausente — rode: sudo ~/vaio-center/install-root.sh"


def run(cmd, timeout=10):
    """Run cmd and return (stdout, error); exactly one of them is None.

    error is CANCELLED when a pkexec authentication prompt was dismissed, which
    callers treat as a normal outcome rather than a failure.
    """
    if not cmd:
        return None, "empty command"
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if proc.returncode == 0:
        return proc.stdout, None
    if cmd[0] == "pkexec" and proc.returncode == PKEXEC_DISMISSED:
        return None, CANCELLED
    if cmd[0] == "pkexec" and proc.returncode == PKEXEC_NOT_AUTHORIZED:
        return None, NOT_AUTHORIZED
    return None, proc.stderr.strip() or f"{cmd[0]} exited with {proc.returncode}"
