"""Run offline tests once and retain machine-readable, measured evidence."""

from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=None,
                        help="parallel test-module processes (default: up to 4)")
    args = parser.parse_args()
    if args.jobs is not None and args.jobs < 1:
        parser.error("--jobs must be at least 1")

    modules = sorted(path.stem for path in (root / "tests").glob("test_*.py"))
    # Keep the shared expensive reference preflights in one process so their
    # process-local cache remains effective. All other test modules are isolated.
    cached = {"test_ambitious_evaluation", "test_general_evaluation",
              "test_native_goals", "test_study"}
    work = [(name,) for name in modules if name not in cached]
    shared = tuple(name for name in modules if name in cached)
    if shared:
        work.append(shared)
    try:
        affinity = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        affinity = os.cpu_count() or 1
    jobs = min(args.jobs or 4, max(1, affinity), len(work))
    start = time.perf_counter()
    results = {}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(run_group, root, group): group for group in work}
        for future in as_completed(futures):
            group = futures[future]
            try:
                group_results = future.result()
            except Exception as error:
                group_results = {name: {"tests_run": 0, "failures": 0, "errors": 1,
                                        "skipped": 0, "output": f"worker failed: {error}"}
                                 for name in group}
            for name, result in group_results.items():
                results[name] = result
    elapsed = time.perf_counter() - start
    tests_run = sum(item["tests_run"] for item in results.values())
    failures = sum(item["failures"] for item in results.values())
    errors = sum(item["errors"] for item in results.values())
    skipped = sum(item["skipped"] for item in results.values())
    stream = "\n".join(results[name]["output"] for name in sorted(results))
    report = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "tests_run": tests_run, "failures": failures, "errors": errors,
        "skipped": skipped, "passed": tests_run - failures - errors - skipped,
        "duration_seconds": elapsed, "successful": failures == 0 and errors == 0,
        "jobs": jobs,
        "test_modules": len(modules),
        "live_api_calls": 0,
        "source_fingerprint": {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                               for folder in ('goalpilot','tests') for p in sorted((root/folder).glob('*.py'))},
        "runner_fingerprint": {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (root / "validate.py", root / "tools/test_worker.py")
        },
        "note": "Adapters in tests are explicit test doubles. Durations are measured on this machine, not performance guarantees.",
    }
    (root / "reports").mkdir(exist_ok=True)
    (root / "reports/tests.txt").write_text(stream + "\n")
    (root / "reports/tests.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["successful"] else 1


def run_group(root, modules):
    started = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(root / "tools/test_worker.py"), *modules],
        cwd=root, capture_output=True, text=True,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        message = (proc.stdout + proc.stderr).strip()
        return {name: {"tests_run": 0, "failures": 0, "errors": 1,
                       "skipped": 0, "duration_seconds": time.perf_counter() - started,
                       "output": f"{name}: worker failed (exit {proc.returncode})\n{message}"}
                for name in modules}
    # Grouped output is identical in each result, but should appear once in the
    # deterministic report. Keep it with the first module in that shard.
    for name in modules[1:]:
        payload[name]["output"] = ""
    return payload


if __name__ == "__main__":
    sys.exit(main())
