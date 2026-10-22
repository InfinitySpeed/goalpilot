"""Execute one isolated unittest shard for validate.py."""
import io
import json
import sys
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(modules):
    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    for module in modules:
        suite.addTests(loader.loadTestsFromName("tests." + module))
    stream = io.StringIO()
    started = time.perf_counter()
    with redirect_stdout(stream), redirect_stderr(stream):
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter() - started
    payload = {}
    # Count each module directly; suites may include loader errors with no tests.
    for module in modules:
        module_suite = loader.loadTestsFromName("tests." + module)
        count = module_suite.countTestCases()
        module_failures = sum(1 for test, _ in result.failures
                              if test.__class__.__module__.endswith(module))
        module_errors = sum(1 for test, _ in result.errors
                            if test.__class__.__module__.endswith(module))
        module_skipped = sum(1 for test, _ in result.skipped
                             if test.__class__.__module__.endswith(module))
        payload[module] = {
            "tests_run": count,
            "failures": module_failures,
            "errors": module_errors,
            "skipped": module_skipped,
            "duration_seconds": elapsed,
            "output": stream.getvalue(),
        }
    # Import/loader errors may not be attributable to a test module; retain
    # them against the shard's first module so the parent cannot report success.
    attributed_errors = sum(item["errors"] for item in payload.values())
    if len(modules) and attributed_errors < len(result.errors):
        payload[modules[0]]["errors"] += len(result.errors) - attributed_errors
    print(json.dumps(payload))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
