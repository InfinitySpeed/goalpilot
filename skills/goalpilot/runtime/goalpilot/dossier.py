"""Bounded local context preparation. Never executes repository code."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import time


IGNORE = {'.git', '.codex', '.aws', '.agents', '.venv', 'venv', 'node_modules', '__pycache__',
          'dist', 'build', '.pytest_cache', '.mypy_cache', '.next', 'coverage'}
SOURCE = {'.py', '.js', '.ts', '.tsx', '.jsx', '.rs', '.go', '.java', '.html', '.css', '.sql', '.sh'}
CONFIG = {'pyproject.toml', 'package.json', 'Cargo.toml', 'go.mod', 'requirements.txt', 'Makefile', 'README', 'README.md', 'AGENTS.md'}


def eligible(path: Path) -> bool:
    name = path.name.lower()
    if name.startswith('.') or any(word in name for word in ('credential', 'secret', 'auth.json')):
        return False
    return path.name in CONFIG or name.startswith('readme.') or path.suffix in SOURCE


def prepare(repo: Path, max_bytes: int = 40000, max_files: int = 64, max_entries: int = 2000,
            *, known_helpers=None) -> dict:
    start = time.monotonic()
    repo = repo.resolve()
    candidates = []
    verified_helpers = []
    visited = 0
    scan_complete = True
    for directory, directories, files in os.walk(repo, followlinks=False):
        directories[:] = sorted(x for x in directories if x not in IGNORE and not (Path(directory)/x).is_symlink())
        visited += len(directories) + len(files)
        if visited > max_entries:
            scan_complete = False
            break
        for name in files:
            path = Path(directory)/name
            if not path.is_symlink() and eligible(path):
                known = (known_helpers or {}).get(str(path.relative_to(repo)))
                if known and path.is_file():
                    # Only exact supplied bytes can use the API in place of a
                    # source dump. Never hide same-named user/modified code.
                    with path.open('rb') as stream:
                        raw = stream.read(known['bytes'] + 1)
                    if len(raw) == known['bytes'] and hashlib.sha256(raw).hexdigest() == known['sha256']:
                        verified_helpers.append({'path':str(path.relative_to(repo)), **known})
                        continue
                candidates.append(path)
    candidates.sort(key=lambda p: (0 if p.name == 'AGENTS.md' else 1 if p.name.lower().startswith('readme') else 2 if p.name in CONFIG else 3,
                                   len(p.relative_to(repo).parts), str(p.relative_to(repo))))
    files = []
    used = 0
    for path in candidates[:max_files]:
        remaining = max_bytes-used
        if remaining <= 0:
            break
        try:
            with path.open('rb') as stream:
                raw = stream.read(min(remaining, 12000)+1)
            truncated = len(raw) > min(remaining, 12000)
            raw = raw[:min(remaining, 12000)]
        except OSError:
            continue
        if b'\0' in raw:
            continue
        used += len(raw)
        files.append({'path':str(path.relative_to(repo)), 'text':raw.decode('utf-8',errors='replace'),
                      'sha256':hashlib.sha256(raw).hexdigest(),'complete':not truncated})
    ancestors = []
    ancestor_checks = []
    for parent in reversed(repo.parents):
        path = parent/'AGENTS.md'
        ancestor_checks.append({'path':str(path),'exists':path.exists(),'symlink':path.is_symlink()})
        if path.is_file() and not path.is_symlink():
            with path.open('rb') as stream:
                raw=stream.read(16001)
            ancestors.append({'path':str(path),'text':raw[:16000].decode('utf-8',errors='replace'),'complete':len(raw)<=16000})
    result = {'repo':str(repo),'files':files,'ancestor_instructions':ancestors,
            'ancestor_checks':ancestor_checks,
            'candidate_paths':[str(p.relative_to(repo)) for p in candidates[:max_entries]],
            'scan_complete':scan_complete, 'all_candidates_included':scan_complete and len(files)==len(candidates) and all(x['complete'] for x in files),
            'source_bytes':used,'duration_seconds':time.monotonic()-start}
    if verified_helpers:
        result['verified_provided_helpers'] = sorted(verified_helpers,key=lambda item:item['path'])
    return result


def render(dossier: dict) -> str:
    lines = [f"LOCAL REPOSITORY SNAPSHOT · cwd={dossier['repo']}",
             "Collected locally immediately before this turn. Instruction-file existence checks have already been performed.",
             "Ancestor AGENTS.md checks: "+'; '.join(f"{x['path']} exists={x['exists']} symlink={x['symlink']}" for x in dossier['ancestor_checks']),
             f"Eligible source paths: {', '.join(dossier['candidate_paths'])}",
             f"Complete snapshot of eligible files: {dossier['all_candidates_included']}. Excluded credentials, caches and generated data are not inventoried."]
    for entry in dossier['ancestor_instructions']:
        lines.extend([f"ANCESTOR INSTRUCTIONS {entry['path']} · complete={entry['complete']}",entry['text']])
    for entry in dossier['files']:
        lines.extend([f"FILE {entry['path']} · sha256={entry['sha256']} · complete={entry['complete']}",entry['text'],f"END FILE {entry['path']}"])
    lines.append("Use the complete unmodified source above instead of repeating pwd/ls/cat. Read additional files when missing, truncated, changed, or needed to resolve a concrete uncertainty. Follow all applicable AGENTS.md instructions. Batch independent reads and checks where appropriate. Build the end-to-end path first; verify relevant behavior and finish once the goal and checks are satisfied. Avoid unrelated features and repeated unchanged tests.")
    return '\n\n'.join(lines)
