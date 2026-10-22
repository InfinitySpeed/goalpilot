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


def _windows_job(proc):
    """Own the complete Windows child tree, including children of exited parents."""
    import ctypes
    from ctypes import wintypes
    class Limits(ctypes.Structure):
        _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                    ('flags', wintypes.DWORD), ('min_set', ctypes.c_size_t),
                    ('max_set', ctypes.c_size_t), ('active', wintypes.DWORD),
                    ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                    ('scheduling', wintypes.DWORD)]
    class Counters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in
                    ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]
    class Extended(ctypes.Structure):
        _fields_ = [('limits', Limits), ('io', Counters), ('process_memory', ctypes.c_size_t),
                    ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t),
                    ('peak_job', ctypes.c_size_t)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    info = Extended()
    info.limits.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if (not kernel.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info))
            or not kernel.AssignProcessToJobObject(handle, wintypes.HANDLE(int(proc._handle)))):
        error = ctypes.WinError(ctypes.get_last_error())
        kernel.CloseHandle(handle)
        raise error
    return kernel, handle


def terminate_group(proc: subprocess.Popen) -> None:
    # Also kill children after a parent exits; they can retain files / run forever.
    if os.name == 'nt':
        job = getattr(proc, '_goalpilot_job', None)
        if job:
            kernel, handle = job
            kernel.CloseHandle(handle)
            proc._goalpilot_job = None
        elif proc.poll() is None:
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    else:
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
            options = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt'
                       else {'start_new_session': True})
            proc = subprocess.Popen(command, cwd=cwd, stdin=input_file, stdout=output, stderr=subprocess.STDOUT, env=env, **options)
            if os.name == 'nt':
                try:
                    proc._goalpilot_job = _windows_job(proc)
                except OSError:
                    proc.kill()
                    proc.wait()
                    raise
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
