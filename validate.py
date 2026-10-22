"""Run offline tests once and retain machine-readable, measured evidence."""

from datetime import datetime, timezone
from contextlib import redirect_stderr, redirect_stdout
import io
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import unittest


def main():
    root = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), top_level_dir=str(root))
    stream = io.StringIO()
    start = time.perf_counter()
    with redirect_stdout(stream), redirect_stderr(stream):
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter() - start
    report = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
        "duration_seconds": elapsed, "successful": result.wasSuccessful(),
        "live_api_calls": 0,
        "source_fingerprint": {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                               for folder in ('goalpilot','tests') for p in sorted((root/folder).glob('*.py'))},
        "note": "Adapters in tests are explicit test doubles. Durations are measured on this machine, not performance guarantees.",
    }
    (root / "reports").mkdir(exist_ok=True)
    (root / "reports/tests.txt").write_text(stream.getvalue())
    (root / "reports/tests.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
