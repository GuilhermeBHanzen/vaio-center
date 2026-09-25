"""`vaio-center` opens the app; `vaio-center --restore` re-applies saved EC settings and exits."""
import sys

from vaio_center import restore
from vaio_center.backend import state


def main(argv=None):
    argv = sys.argv if argv is None else argv
    if "--restore" in argv[1:]:
        errors = restore.restore(state.load())
        for error in errors:
            print(f"vaio-center: {error}", file=sys.stderr)
        return 1 if errors else 0
    from vaio_center.app import VaioCenter

    return VaioCenter().run(argv[:1])


if __name__ == "__main__":
    sys.exit(main())
