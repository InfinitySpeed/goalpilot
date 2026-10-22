"""Local calling-session protocol. No adapter, model request, or completion claim."""
from __future__ import annotations

from contextlib import contextmanager
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

from . import __version__
from .engine import atomic_json, artifacts_intact, lock, verify
from .gates import make_gate
from .model import ContractError, digest, positive, validate
from .originals import capture, intact
from .reuse import inventory
from .gates import IGNORE


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def location(repo, run):
    repo, run = Path(repo).resolve(), Path(run).absolute()
    if not repo.is_dir():
        raise ContractError('Repository directory does not exist')
    if any(p.is_symlink() for p in (run, *run.parents)):
        raise ContractError('Evidence path must not contain symlinks')
    run = run.resolve()
    if run == repo or repo in run.parents or run in repo.parents:
        raise ContractError('Evidence must be outside and separate from repository')
    return repo, run


def sealed_write(run, name, value):
    atomic_json(run / name, value)
    atomic_json(run / (name + '.sha256'), {'sha256': sha(run / name)})


def sealed_read(run, name):
    path = run / name
    receipt = run / (name + '.sha256')
    if path.is_symlink() or receipt.is_symlink() or sha(path) != json.loads(receipt.read_text())['sha256']:
        raise ContractError(f'Integrity mismatch: {name}')
    return json.loads(path.read_text())


def test_inventory(repo):
    root = Path(repo) / 'tests'
    if root.is_symlink():
        raise ContractError('Symlink tests are unsupported')
    result = {}
    for p in sorted(root.rglob('*')):
        if '__pycache__' in p.parts:
            continue
        if p.is_symlink():
            raise ContractError('Symlink tests are unsupported')
        if p.is_file():
            result[str(p.relative_to(repo))] = sha(p)
    return result


def save(run, state):
    state['elapsed_seconds'] = max(0, time.time() - state['started_at'])
    sealed_write(run, 'session-state.json', state)



def render_context(dossier):
    lines=['INITIAL REPOSITORY: '+dossier['repo'],
           'AGENTS existence checks: '+', '.join(x['path']+'='+str(x['exists'])for x in dossier['ancestor_checks']),
           'Complete eligible source='+str(dossier['all_candidates_included'])+'; scan complete='+str(dossier['scan_complete'])+
           '. Credentials/caches/non-source data not shown. Read missing/truncated/changed files, follow applicable instructions.']
    for item in dossier['ancestor_instructions']:
        lines.extend(['INSTRUCTIONS '+item['path']+' complete='+str(item['complete']),item['text']])
    if dossier.get('verified_provided_helpers'):
        lines.append('Verified supplied helpers omitted from source context (exact hashes checked; API below): '+
                     ', '.join(x['path']for x in dossier['verified_provided_helpers']))
    for item in dossier['files']:
        lines.extend(['FILE '+item['path']+' complete='+str(item['complete']),item['text']])
    lines.append('Use supplied complete source directly; avoid duplicate pwd/ls/find/cat.')
    return '\n'.join(lines)


def start(goal_file, repo, run_dir, *, wall_seconds=900, max_verifications=5,
          max_tokens=None, max_uncached_tokens=None, helpers=False, context=False):
    # All input validation precedes even mkdir / lock creation.
    raw = Path(goal_file).read_bytes()
    goal = raw.decode('utf-8')
    if not goal.strip() or '\0' in goal:
        raise ContractError('Goal must be nonempty UTF-8 without NUL')
    repo, run = location(repo, run_dir)
    positive(wall_seconds, 'wall_seconds')
    if type(max_verifications) is not int or max_verifications < 1:
        raise ContractError('max_verifications must be a positive integer')
    for name, value in (('max_tokens', max_tokens), ('max_uncached_tokens', max_uncached_tokens)):
        if value is not None:
            positive(value, name)
            if type(value) is not int:
                raise ContractError(f'{name} must be an integer')
    if run.exists():
        raise ContractError('Run directory already exists; use its frozen session')
    if helpers:
        from .support import validate_runtime
        validate_runtime(repo)
    from .hooks import preflight
    preflight(repo, hashlib.sha256(raw).hexdigest())
    started = time.time()
    run.mkdir(parents=True, mode=0o700)
    with lock(run / 'session.lock'):
        (run / 'goal.bin').write_bytes(raw)
        snapshot = capture(repo, run / 'originals', max_files=2000, max_bytes=64000000, max_entries=12000)
        gate = make_gate(repo, run, snapshot) if snapshot['within_limits'] and not snapshot['omitted'] else None
        contract = {'protocol': 1, 'engine_version': __version__, 'goal': goal,
                    'goal_sha256': sha(run / 'goal.bin'), 'repo': str(repo), 'run_dir': str(run),
                    'budget': {'wall_seconds': wall_seconds, 'max_verifications': max_verifications,
                               'max_tokens': max_tokens, 'max_uncached_tokens': max_uncached_tokens},
                    'original_snapshot': snapshot, 'original_gate': gate,
                    'original_tests': test_inventory(repo), 'scope': 'inferred'}
        initial_context = None
        if context:
            from .dossier import prepare
            known = None
            if helpers and gate:
                from .support import validate_runtime
                known = {}
                for name, source in validate_runtime(repo).items():
                    raw = Path(__file__).with_name(source).read_bytes()
                    known[name] = {'sha256':hashlib.sha256(raw).hexdigest(), 'bytes':len(raw)}
            dossier = prepare(repo, max_bytes=12000, max_files=32, max_entries=2000, known_helpers=known)
            sealed_write(run, 'initial-context.json', dossier)
            contract['context'] = {'path': str(run / 'initial-context.json'), 'sha256': sha(run / 'initial-context.json')}
            initial_context = 'ORIGINAL GOAL (verbatim):\n' + goal + '\n\n' + render_context(dossier) + '\nThis is the INITIAL source snapshot, before optional helper provisioning; use the supplied skill API for those helpers.'
        if helpers and gate:
            from .support import provision_runtime
            contract['helpers'] = provision_runtime(repo)
            if initial_context is not None:
                from .runtime_kit import API
                initial_context += '\n\n' + API
        sealed_write(run, 'session.json', contract)
        state = {'status': 'ready' if gate else 'unsupported', 'closed': False,
                 'started_at': started, 'verifications': [], 'events': [],
                 'engine_model_calls': 0, 'caller_usage': 'UNKNOWN', 'total_tokens': None,
                 'usage_scope': 'Caller measured externally; token budgets require external enforcement',
                 'active_seconds': time.time() - started}
        state['events'].append({'action': 'start', 'at': started, 'pid': os.getpid(), 'lock': 'exclusive'})
        save(run, state)
        from .hooks import bind
        attached = bind(run)
        if attached:
            state['completion_owner'] = 'codex_stop_hook'
            save(run, state)
        result = compact(run, contract, state)
        if initial_context is not None:
            result['initial_context'] = initial_context
        return result


def load(run):
    run = Path(run).absolute()
    # Never recreate a missing session or its lock on resume.
    if not run.is_dir() or any(p.is_symlink() for p in (run, *run.parents)):
        raise ContractError('Missing or symlink session directory')
    if (run / 'session.lock').is_symlink():
        raise ContractError('Symlink session lock')
    contract = sealed_read(run, 'session.json')
    repo, resolved = location(contract['repo'], run)
    if str(repo) != contract['repo']:
        raise ContractError('Repository moved or redirected; refusing scope change')
    if contract['run_dir'] != str(resolved):
        raise ContractError('Session moved; refusing silent scope change')
    state = sealed_read(run, 'session-state.json')
    return resolved, contract, state


def integrity(run, contract):
    if sha(run / 'goal.bin') != contract['goal_sha256'] or (run / 'goal.bin').is_symlink():
        raise ContractError('Original goal bytes changed')
    if not intact(contract['original_snapshot']):
        raise ContractError('Original source snapshot changed')
    if contract.get('context') and not artifacts_intact({'artifacts': [contract['context']]}):
        raise ContractError('Initial context artifact changed')
    if not artifacts_intact({'artifacts': contract.get('helpers', [])}):
        raise ContractError('Provisioned helper changed; restore its frozen bytes')
    gate = contract['original_gate']
    if gate and not artifacts_intact(gate):
        raise ContractError('Original gate changed')
    if (run / 'acceptance.json').exists():
        acceptance = sealed_read(run, 'acceptance.json')
        if not artifacts_intact(acceptance):
            raise ContractError('Frozen builder acceptance changed')
        if test_inventory(contract['repo']) != acceptance['tests']:
            raise ContractError('Builder tests changed during repair; restore frozen tests')
        return acceptance
    return None


@contextmanager
def session(run_dir, action):
    run, contract, _ = load(run_dir)
    with lock(run / 'session.lock'):
        run, contract, state = load(run)
        begun = time.monotonic()
        try:
            if state.get('acceptance_sha256') and sha(run / 'acceptance.json') != state['acceptance_sha256']:
                raise ContractError('Frozen acceptance changed or missing')
            acceptance = integrity(run, contract)
            if state['closed'] and inventory(contract['repo'], exclude=IGNORE) != state.get('verified_source'):
                state['status'], state['closed'] = 'source_drift', False
        except (OSError, ValueError, KeyError, TypeError) as exc:
            state['status'], state['closed'] = 'integrity_failed', False
            state['error'] = str(exc)
            save(run, state)
            raise ContractError(str(exc)) from exc
        state['events'].append({'action': action, 'at': time.time(), 'pid': os.getpid(), 'lock': 'exclusive'})
        try:
            yield run, contract, state, acceptance
        finally:
            state['active_seconds'] += time.monotonic() - begun
            save(run, state)


def remaining(contract, state):
    return contract['budget']['wall_seconds'] - (time.time() - state['started_at'])


def expired(contract, state):
    if remaining(contract, state) <= 0 or len(state['verifications']) >= contract['budget']['max_verifications']:
        state['status'], state['closed'] = 'budget_exhausted', False
        return True
    return False


def submit(run_dir, handoff_file, *, suite_only=False):
    # Parse before any writes. Invalid submissions never consume the first freeze.
    raw = Path(handoff_file).read_bytes()
    handoff = json.loads(raw.decode('utf-8'))
    if not isinstance(handoff, dict) or not isinstance(handoff.get('summary'), str):
        raise ContractError('Handoff needs summary and executable checks')
    with session(run_dir, 'submit') as (run, contract, state, acceptance):
        candidate = validate({'goal': contract['goal'], 'repo': contract['repo'],
                              'checks': ([{'id': 'internal', 'description': 'Validate suite-only submission schema', 'command': [sys.executable, '-c', 'pass'], 'timeout_seconds': 1}] if suite_only else handoff.get('checks')),
                              'assumptions': handoff.get('assumptions', []),
                              'limitations': handoff.get('limitations', [])})
        if acceptance:
            raise ContractError('Acceptance already frozen; repair then verify with the SAME checks')
        if expired(contract, state):
            return compact(run, contract, state)
        if not contract['original_gate']:
            state['status'] = 'unsupported'
            return compact(run, contract, state)
        if any(c['id'] in ('original-tests', 'builder-tests') for c in candidate['checks']):
            raise ContractError('Reserved check ID')
        current = test_inventory(contract['repo'])
        # Stronger tests may append assertions to original tests. Originals remain
        # separately executable: the builder gate never replaces the original gate.
        builder = run / 'builder'
        builder.mkdir(exist_ok=False)
        try:
            snapshot = capture(contract['repo'], builder / 'originals', max_files=2000,
                               max_bytes=64000000, max_entries=12000)
            gate = make_gate(contract['repo'], builder, snapshot)
            if not gate or not snapshot['within_limits'] or snapshot['omitted']:
                raise ContractError('Cannot freeze a complete supported builder test gate')
            # Strengthened suites may take longer than initial regressions.
            # Set their limit BEFORE first acceptance; original frozen gate,
            # mission deadline and later repair budgets stay unchanged.
            gate['check']['timeout_seconds'] = min(120, contract['budget']['wall_seconds'])
        except BaseException:
            shutil.rmtree(builder)
            raise
        if suite_only:
            candidate['checks'] = []
        checks = [contract['original_gate']['check'],
                  {**gate['check'], 'id': 'builder-tests'}, *candidate['checks']]
        if len({c['id'] for c in checks}) != len(checks):
            raise ContractError('Reserved or duplicate check ID')
        frozen = {'repo': contract['repo'], 'goal': contract['goal'], 'scope': 'inferred',
                  'checks': checks, 'tests': current,
                  'artifacts': contract['original_gate']['artifacts'] + gate['artifacts'],
                  'handoff': handoff, 'handoff_sha256': hashlib.sha256(raw).hexdigest()}
        # A supplied Python assertion script is acceptance, not repairable code.
        # Inline programs are already immutable JSON; unittest uses frozen tests.
        for index, check in enumerate(candidate['checks']):
            command = check['command']
            if len(command) < 2 or not Path(command[0]).name.startswith('python'):
                continue
            script_index = next((i for i in range(1, len(command))
                                 if not command[i].startswith('-')), None)
            if script_index is None or '-c' in command[:script_index] or '-m' in command[:script_index]:
                continue
            source = Path(command[script_index])
            source = source if source.is_absolute() else Path(contract['repo']) / source
            if source.suffix != '.py' or not source.is_file() or source.is_symlink():
                continue
            target = run / f'check-{index}.py'
            target.write_bytes(source.read_bytes())
            command[script_index] = str(target)
            frozen['artifacts'].append({'path': str(target), 'sha256': sha(target)})
        # No command executes before the final acceptance is sealed.
        sealed_write(run, 'acceptance.json', frozen)
        state['acceptance_sha256'] = sha(run / 'acceptance.json')
        state['status'], state['closed'] = 'awaiting_verification', False
        return compact(run, contract, state)


def verify_session(run_dir):
    with session(run_dir, 'verify') as (run, contract, state, acceptance):
        if not acceptance:
            raise ContractError('Submit executable checks before verification')
        if expired(contract, state):
            return compact(run, contract, state)
        record = {'started_at': time.time(), 'status': 'running', 'checks': []}
        state['verifications'].append(record)
        state['status'], state['closed'] = 'verifying', False
        save(run, state)  # Interrupted commands retain their attempt and budget.
        begun = time.monotonic()
        try:
            before = inventory(contract['repo'], exclude=IGNORE)
            record['source_sha256'] = digest(before)
            results = verify(acceptance, time.monotonic() + remaining(contract, state),
                             run / 'evidence' / str(len(state['verifications'])))
            integrity(run, contract)  # Detect check-induced drift as well.
            after = inventory(contract['repo'], exclude=IGNORE)
            if after != before:
                raise ContractError('Verification mutated repository inputs')
            passed = bool(results) and all(r['passed'] for r in results)
            state['status'] = ('scope_passed' if passed else
                               'verification_unavailable' if any(r.get('infrastructure_error') for r in results) else
                               'timed_out' if any(r.get('timed_out') for r in results) else 'failed')
            state['closed'] = passed and remaining(contract, state) > 0
            if passed and not state['closed']:
                state['status'] = 'budget_exhausted'
            if state['closed']:
                state['verified_source'] = after
            record.update(checks=results, status=state['status'])
        except BaseException as exc:
            state['status'], state['closed'] = ('interrupted' if isinstance(exc, KeyboardInterrupt) else 'integrity_failed'), False
            record.update(status=state['status'], error=str(exc))
            raise
        finally:
            record['duration_seconds'] = time.monotonic() - begun
        return compact(run, contract, state)



def finish(run_dir):
    """Freeze the complete current suite and verify, without a generated handoff.

    Calling again repairs against the SAME frozen tests and consumes another
    verification. Never substitutes a new gate or resets the session deadline.
    """
    current = status(run_dir)  # Validate integrity/budget BEFORE writing any handoff.
    if current['closed'] or current['status'] in ('unsupported', 'budget_exhausted'):
        return current
    run, contract, state = load(run_dir)
    if not state.get('acceptance_sha256'):
        # A real test gate is mandatory. The handoff records the honest scope:
        # existing + current tests, not a promise of semantic completeness.
        handoff = run / 'suite-handoff.json'
        if handoff.exists() or handoff.is_symlink():
            raise ContractError('Unsubmitted finish artifact exists; inspect instead of overwriting')
        atomic_json(handoff, {
            'summary': 'Verify original regressions and the full frozen current unittest suite',
            'limitations': ['Suite passing is local evidence; independent evaluation must judge the full natural-language goal.'],
            'checks': []})
        result = submit(run, handoff, suite_only=True)
        if result['status'] != 'awaiting_verification':
            return result
    return verify_session(run)


def repair(run_dir):
    with session(run_dir, 'repair') as (run, contract, state, acceptance):
        if not acceptance:
            raise ContractError('No frozen acceptance; submit first')
        if not expired(contract, state):
            state['status'], state['closed'] = 'repairing', False
        return compact(run, contract, state)


def status(run_dir):
    with session(run_dir, 'status') as (run, contract, state, acceptance):
        if not state['closed'] and remaining(contract, state) <= 0:
            state['status'] = 'budget_exhausted'
        if state['status'] == 'verifying':
            state['status'], state['closed'] = 'interrupted', False
        return compact(run, contract, state)


def compact(run, contract, state):
    latest = state['verifications'][-1]['checks'] if state['verifications'] else []
    result = {'status': state['status'], 'closed': state['closed'], 'run_dir': str(run),
              'checks_passed': sum(x['passed'] for x in latest), 'checks_total': len(latest),
              'attempts': len(state['verifications']), 'elapsed_seconds': round(time.time() - state['started_at'], 3),
              'engine_model_calls': 0, 'caller_usage': 'UNKNOWN', 'total_tokens': None,
              'details': str(run / 'session-state.json'),
              'completion_owner': state.get('completion_owner', 'calling_model')}
    failed = [x for x in latest if not x['passed']]
    if failed:
        result['failures'] = [{'id': x['id'], 'output': x.get('output', '')[-1600:],
                               'log': x.get('log'), 'timed_out': x.get('timed_out', False),
                               'infrastructure_error': x.get('infrastructure_error', False)} for x in failed]
        records = state['verifications']
        if len(records) > 1 and records[-1].get('source_sha256') and records[-1].get('source_sha256') == records[-2].get('source_sha256'):
            result['next_action'] = 'Repeated verification without source changes. Isolate the failing assertion/environment cause before another full run; keep all frozen acceptance.'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='GoalPilot in-session: local protocol, no nested model')
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('start')
    p.add_argument('--goal-file', type=Path, required=True)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--run-dir', type=Path, required=True)
    p.add_argument('--wall-seconds', type=float, default=900)
    p.add_argument('--max-verifications', type=int, default=5)
    p.add_argument('--max-tokens', type=int)
    p.add_argument('--max-uncached-tokens', type=int)
    p.add_argument('--helpers', action='store_true')
    p.add_argument('--context', action='store_true')
    for action in ('submit', 'verify', 'status', 'repair', 'finish', 'check'):
        p = sub.add_parser(action)
        p.add_argument('run_dir', type=Path)
        if action == 'submit':
            p.add_argument('--handoff', type=Path, required=True)
        if action == 'check':
            p.add_argument('--timeout', type=float, default=60)
            p.add_argument('command', nargs=argparse.REMAINDER)
    args = vars(parser.parse_args(argv))
    action = args.pop('action')
    try:
        if action == 'start':
            result = start(**args)
        elif action == 'submit':
            result = submit(args['run_dir'], args['handoff'])
        elif action == 'check':
            from .monitor import run_check
            command = args['command']
            result = run_check(args['run_dir'], command[1:] if command[:1] == ['--'] else command, timeout=args['timeout'])
        else:
            result = {'verify': verify_session, 'status': status, 'repair': repair, 'finish': finish}[action](args['run_dir'])
        initial_context = result.pop('initial_context', None)
        print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
        if initial_context is not None:
            print(initial_context)
        return 0 if result['status'] in ('ready', 'awaiting_verification', 'repairing', 'scope_passed', 'passed') else 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'refused', 'closed': False, 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
