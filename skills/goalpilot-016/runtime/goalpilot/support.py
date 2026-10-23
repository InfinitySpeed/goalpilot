"""Provision reusable test plumbing locally instead of asking a model to emit it."""
import hashlib
from pathlib import Path
from .model import ContractError


def provision(repo):
    source=Path(__file__).with_name('probe_helpers.py').read_bytes()
    path=Path(repo)/'goalpilot_support.py'
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_bytes()!=source:
            raise ContractError('goalpilot_support.py already exists with different contents')
    else:
        path.write_bytes(source)
    return {'path':str(path),'sha256':hashlib.sha256(source).hexdigest()}


GUIDE='''
The host provided goalpilot_support.py, a portable stdlib test utility. Do not edit it.
from goalpilot_support import dispatch, rejects, jsonl, json_http
c=dispatch(service.call, **defaults); c(operation, **overrides) merges the argument dict.
rejects(lambda: c('operation', ...)) asserts ValueError.
jsonl(argv, packets, cwd=None, timeout=8) runs a JSONL program and returns decoded replies.
with json_http(argv, cwd=None, timeout=7) as request:
    request('GET','/health'); request('POST','/api', packet, status=400)
The HTTP helper expects the program to announce {"port":PORT} on its first stdout line,
then performs bounded real localhost requests and always terminates the process group.
Use these helpers where applicable; business assertions must still come from the README.
Write concise table-driven regression journeys covering EVERY original workflow, negative
cases, persistence and actual CLI/HTTP behavior. Avoid repeated subprocess/server fixtures.
Keep the complete documented behavior and existing tests. Budget generated code carefully:
aim for <=10000 output tokens including patches, tests and handoff. This is an efficiency
target, not permission to omit requirements, validations, maintainability or tests.
Reuse existing storage/transport. Patch only changed regions; never re-emit a whole file
for a small correction. Do not recopy unchanged source into terminal output. Preserve the
existing detailed README; change documentation only where implementation actually needs it.
Run relevant non-network tests once after implementation, then only failing checks after
repairs. The host runs the complete frozen suite, including real HTTP tests. Report any
sandbox restriction honestly. Finish immediately when all original workstreams are done.
'''


def validate_runtime(repo):
    """Check collisions without editing the project or creating evidence."""
    sources = {'goalpilot_runtime.py': 'runtime_kit.py', 'goalpilot_support.py': 'probe_helpers.py'}
    # Validate ALL collisions before any writes.
    for name, source in sources.items():
        path = Path(repo) / name
        if path.is_symlink() or path.exists() and (not path.is_file() or path.read_bytes() != Path(__file__).with_name(source).read_bytes()):
            raise ContractError(f'{name} already exists with different contents')
    return sources


def provision_runtime(repo):
    """Opt-in portable plumbing, installed only after original source capture."""
    sources = validate_runtime(repo)
    receipts = []
    for name, source in sources.items():
        path = Path(repo) / name
        raw = Path(__file__).with_name(source).read_bytes()
        if not path.exists():
            path.write_bytes(raw)
        receipts.append({'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()})
    return receipts
