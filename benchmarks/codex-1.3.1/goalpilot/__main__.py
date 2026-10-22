from .cli import main
import signal

def interrupt(signum, frame):
    raise KeyboardInterrupt

signal.signal(signal.SIGTERM, interrupt)

raise SystemExit(main())
