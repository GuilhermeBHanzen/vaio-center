"""Single place where the app runs external commands."""
import subprocess

CANCELLED = "cancelled"
PKEXEC_DISMISSED = (126, 127)


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
    if cmd[0] == "pkexec" and proc.returncode in PKEXEC_DISMISSED:
        return None, CANCELLED
    return None, proc.stderr.strip() or f"{cmd[0]} exited with {proc.returncode}"
