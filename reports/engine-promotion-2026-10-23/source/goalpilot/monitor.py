"""Passive local command journal: no inference, retries, success claims or shell."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
import time

from .engine import atomic_json
from .model import ContractError, digest, positive
from .process import run_process
from .reuse import inventory
from .gates import IGNORE


def advise(history, current):
    """Identical observations require a new hypothesis; changed code resets a streak."""
    same = []
    for previous in reversed(history):
        if previous.get('after') != current['before']:
            break
        if previous.get('signature') == current['signature']:
            same.append(previous)
        else:
            break
    repeats = len(same) + 1
    failed = current['returncode'] != 0 or current['timed_out']
    if not failed:
        return {'kind': 'passed', 'repetitions': repeats, 'intervention': False}
    unchanged = current['before'] == current['after']
    kind = 'stalled' if unchanged and repeats >= 2 else 'failed'
    output = current['output']
    if current.get('launch_error'):
        hint = 'Executable unavailable. Check the local tool/environment once; repeating this command cannot install it.'
    elif current['timed_out']:
        hint = 'Bounded command timed out. Isolate the slow step and inspect its termination/IO; do not repeat unchanged.'
    elif 'ModuleNotFoundError' in output:
        hint = 'Import failure. Check the documented project invocation, cwd and installed dependency; repair the cause before rerunning.'
    else:
        hint = 'Read the failing assertion and repair its implementation. Run that failing case before the full suite; preserve all acceptance.'
    return {'kind': kind, 'repetitions': repeats, 'intervention': kind == 'stalled',
            'next_action': hint, 'closed': False}


def stable_output(output):
    # Unittest's duration footer is observational noise, not an error value.
    return '\n'.join(line for line in output.splitlines()
                     if not re.fullmatch(r'Ran \d+ tests? in \d+(?:\.\d+)?s', line))


def run_check(run_dir, command, *, timeout=60):
    # Import lazily: this helper cannot construct a model adapter or RPC session.
    from .session import session, remaining, save
    if not isinstance(command, list) or not command or any(not isinstance(x, str) or '\0' in x for x in command):
        raise ContractError('Check requires a nonempty argv array')
    positive(timeout, 'timeout')
    with session(run_dir, 'check') as (run, contract, state, acceptance):
        left = remaining(contract, state)
        if left <= 0:
            state['status'], state['closed'] = 'budget_exhausted', False
            return {'status': 'budget_exhausted', 'closed': False, 'executed': False}
        # Capture a reservation before executing: killed checks are not silently retried.
        history = state.setdefault('observations', [])
        if len(history) >= 1000:
            raise ContractError('Observation limit reached; preserve the existing session')
        before = digest(inventory(contract['repo'], exclude=IGNORE))
        record = {'command': command, 'before': before, 'started_at': time.time(), 'status': 'running'}
        history.append(record)
        save(run, state)
        log = run / 'observations' / f'{len(history)}.log'
        result = run_process(command, Path(contract['repo']), min(timeout, left), log_path=log)
        if result.launch_error:
            log.write_text(result.output + '\n')
        record.update(after=digest(inventory(contract['repo'], exclude=IGNORE)),
                      returncode=result.returncode, timed_out=result.timed_out,
                      launch_error=result.launch_error, output=result.output[-2000:],
                      duration_seconds=result.duration_seconds, log=str(log), status='observed')
        # No path/number normalization: different errors must not be collapsed.
        record['signature'] = digest({'command': command, 'before': before, 'after': record['after'],
                                      'code': result.returncode, 'timeout': result.timed_out,
                                      'output_sha256': hashlib.sha256(stable_output(result.output).encode()).hexdigest()})
        advice = advise(history[:-1], record)
        record['advice'] = advice
        state['closed'] = False  # This is diagnostic work, never acceptance.
        if state['status'] == 'scope_passed':
            state['status'] = 'working'
        return {'status': advice['kind'], 'closed': False, 'executed': True,
                'returncode': result.returncode, 'seconds': round(result.duration_seconds, 3),
                'output': '' if advice['intervention'] else record['output'],
                'log': str(log), **advice}
