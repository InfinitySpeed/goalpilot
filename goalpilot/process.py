"""Deadline-aware subprocesses, bounded output and whole-process-group cleanup."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import threading
import time


@dataclass
class ProcessResult:
    returncode: int
    output: str
    duration_seconds: float
    timed_out: bool = False
    output_truncated: bool = False
    launch_error: bool = False


def terminate_group(proc: subprocess.Popen) -> None:
    # Also kill children after a parent exits; they can retain files / run forever.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()


def run_process(command: list[str], cwd: Path, timeout: float, *, stdin: str = "", log_path: Path | None = None, max_bytes: int = 131072, env: dict[str, str] | None = None) -> ProcessResult:
    start = time.monotonic()
    if timeout <= 0:
        return ProcessResult(124, "Deadline exhausted", 0, True)
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    output_file = open(log_path, "w+b") if log_path else tempfile.TemporaryFile()
    with output_file as output, tempfile.TemporaryFile() as input_file:
        input_file.write(stdin.encode())
        input_file.seek(0)
        try:
            proc = subprocess.Popen(command, cwd=cwd, stdin=input_file, stdout=output, stderr=subprocess.STDOUT, start_new_session=True, env=env)
        except OSError as exc:
            return ProcessResult(127, f"{type(exc).__name__}: {exc}", time.monotonic() - start, launch_error=True)
        timed_out = False
        # Popen.wait(timeout) polls with sleeps up to 50 ms. A blocking reaper
        # thread avoids that fixed latency for the many short local checks.
        finished = threading.Event()
        def reap():
            try:
                proc.wait()
            finally:
                finished.set()
        waiter = threading.Thread(target=reap, daemon=True)
        waiter.start()
        try:
            timed_out = not finished.wait(timeout=max(0, timeout - (time.monotonic() - start)))
        finally:
            terminate_group(proc)
            waiter.join(timeout=1)
        output.flush()
        size = output.seek(0, 2)
        output.seek(max(0, size - max_bytes))
        tail = output.read().decode(errors="replace")
        return ProcessResult(124 if timed_out else proc.returncode, tail, time.monotonic() - start, timed_out, size > max_bytes)
