"""Bounded repository metadata snapshots: activity is not proof of progress."""

from __future__ import annotations

import os
from pathlib import Path


IGNORED = {".git", "node_modules", ".venv", "venv", "__pycache__", "build", "dist", ".mypy_cache", ".pytest_cache"}


def snapshot(repo: Path, limit: int = 2000) -> tuple[dict, bool]:
    entries = {}
    complete = True

    def on_error(error):
        nonlocal complete
        complete = False

    for directory, directories, files in os.walk(repo, followlinks=False, onerror=on_error):
        directories[:] = sorted(x for x in directories if x not in IGNORED and not (Path(directory) / x).is_symlink())
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_symlink():
                continue
            if len(entries) >= limit:
                return entries, False
            try:
                stat = path.stat()
                # No file contents, credentials or source text are read here.
                entries[str(path.relative_to(repo))] = (stat.st_size, stat.st_mtime_ns)
            except OSError:
                complete = False
    return entries, complete


def changes(before: tuple[dict, bool], after: tuple[dict, bool]) -> dict:
    old, old_complete = before
    new, new_complete = after
    changed = sorted(key for key in old.keys() | new.keys() if old.get(key) != new.get(key))
    return {"changed_files": changed[:50], "changed_file_count": len(changed),
            "complete": old_complete and new_complete,
            "interpretation": "Metadata activity only; not proof of correct implementation or progress toward the goal."}
