"""`vaio-center` opens the app; `vaio-center --restore` re-applies saved EC settings and exits;
`vaio-center --fan-auto` hands the fans back to the EC and exits; `vaio-center --daemon` runs
the background service (Fn backlight hotkeys and fan modes).
"""
import sys

from vaio_center import restore
from vaio_center.backend import state, wmi


def main(argv=None):
    argv = sys.argv if argv is None else argv
    if "--restore" in argv[1:]:
        errors = restore.restore(state.load())
        for error in errors:
            print(f"vaio-center: {error}", file=sys.stderr)
        return 1 if errors else 0
    if "--fan-auto" in argv[1:]:
        error = wmi.set_fan_auto()
        if error:
            print(f"vaio-center: {error}", file=sys.stderr)
        return 1 if error else 0
    if "--daemon" in argv[1:]:
        from vaio_center.daemon import Daemon

        return Daemon().run()
    from vaio_center.app import VaioCenter

    return VaioCenter().run(argv[:1])


if __name__ == "__main__":
    sys.exit(main())
