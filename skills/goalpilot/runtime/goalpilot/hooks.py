"""Local Codex command hooks. Never constructs a model, grants permission or retries.

Inactive sessions only get a small capability beacon. Active sessions journal real
commands and verify at Stop. Only actual failed acceptance requests a continuation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from .engine import atomic_json, lock
from .model import ContractError, digest
from .gates import IGNORE
from .reuse import inventory
from .monitor import stable_output


def root():
    path = Path(os.environ.get('GOALPILOT_HOOK_STATE_DIR', str(Path.home()/'.goalpilot/hooks')))
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ContractError('Hook registry must not contain symlinks')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def key(session_id):
    if not isinstance(session_id, str) or not session_id or len(session_id) > 256:
        raise ContractError('Invalid Codex session identifier')
    return hashlib.sha256(session_id.encode()).hexdigest()


def code_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def read(path):
    if path.is_symlink():
        raise ContractError('Symlink hook registry entry')
    return json.loads(path.read_text()) if path.exists() else None



def preflight(repo, goal_sha256):
    session_id=os.environ.get('CODEX_THREAD_ID')
    if not session_id:return
    folder=root();beacon=read(folder/(key(session_id)+'.beacon.json'))
    if not beacon or beacon.get('code_sha256')!=code_hash() or time.time()-beacon['at']>120 or beacon['cwd']!=str(Path(repo).resolve()):return
    previous=read(folder/(key(session_id)+'.binding.json'))
    if previous:
        from .session import status
        if not status(previous['run_dir'])['closed'] and (previous.get('active',True) or previous['goal_sha256']==goal_sha256):
            raise ContractError('Codex thread already owns an open GoalPilot goal: '+previous['run_dir']+'; resume it without resetting goal/deadline/budget')


def retire(binding):
    folder=root();path=folder/(key(binding['session_id'])+'.binding.json')
    with lock(folder/'registry.lock'):
        current=read(path)
        if current and current['run_dir']==binding['run_dir']:
            current.update(active=False,retired_at=time.time());atomic_json(path,current)


def bind(run):
    """Attach ONLY when this exact engine already observed this Codex thread."""
    session_id = os.environ.get('CODEX_THREAD_ID')
    if not session_id:
        return None
    folder = root()
    beacon = read(folder/(key(session_id)+'.beacon.json'))
    if not beacon or beacon.get('code_sha256') != code_hash() or time.time()-beacon['at'] > 120:
        return None
    from .session import load
    run, contract, state = load(run)
    if beacon['cwd'] != contract['repo']:
        return None
    path = folder/(key(session_id)+'.binding.json')
    with lock(folder/'registry.lock'):
        previous = read(path)
        if previous and previous['run_dir'] != str(run):
            from .session import status
            if not status(previous['run_dir'])['closed'] and (previous.get('active',True) or previous['goal_sha256']==contract['goal_sha256']):
                raise ContractError('Codex thread already owns an open GoalPilot goal; resume it, do not reset its budget')
        binding = {'session_id':session_id,'run_dir':str(run),'repo':contract['repo'],
                   'goal_sha256':contract['goal_sha256'],'code_sha256':code_hash(),'bound_at':time.time(),'active':True}
        atomic_json(path,binding)
    return binding


def active(event):
    folder=root();session_id=event['session_id'];binding=read(folder/(key(session_id)+'.binding.json'))
    if not binding or not binding.get('active',True):
        return None
    if binding['repo'] != str(Path(event['cwd']).resolve()) or binding['code_sha256'] != code_hash():
        raise ContractError('Hook binding moved or engine changed')
    from .session import load
    _,contract,_=load(binding['run_dir'])
    if contract['goal_sha256'] != binding['goal_sha256']:
        raise ContractError('Hook goal integrity changed')
    return binding



def exit_code(value):
    if not isinstance(value,dict):return None
    for field in ('exit_code','exitCode','returncode','return_code'):
        code=value.get(field)
        if type(code)is int:return code
    for field in ('metadata','process','exit'):
        nested=value.get(field)
        code=exit_code(nested)
        if code is not None:return code
    return None


def shape(value, depth=0):
    if isinstance(value,dict) and depth<3:
        return {str(k):shape(v,depth+1)for k,v in value.items()}
    return type(value).__name__


def response(value):
    """Read documented/model-facing exec results; unknown formats never imply failure."""
    if isinstance(value,dict):
        code=exit_code(value)
        output=next((value[k] for k in ('output','stdout','aggregatedOutput') if isinstance(value.get(k),str)),None)
        if output is not None:
            return code,output
        # MCP/local tools may supply an ordinary text content array.
        if isinstance(value.get('content'),list):
            return response('\n'.join(x.get('text','')for x in value['content']if isinstance(x,dict)and x.get('type')=='text'))
        return None,json.dumps(value,ensure_ascii=False)
    if isinstance(value,str):
        try:
            decoded=json.loads(value)
        except ValueError:
            decoded=None
        if isinstance(decoded,dict):
            return response(decoded)
        match=re.search(r'(?:Process exited with code|Exit code:|exit_code[=:])\s*(-?\d+)',value)
        return int(match.group(1))if match else None,value
    return None,''



def test_failure(output):
    # Codex Bash hooks currently send stdout/stderr as a string without an exit
    # code. Recognize a completed unittest failure summary, never arbitrary
    # error words or JSON payload fields. Exit code remains UNKNOWN in evidence.
    return bool(re.search(r'^FAILED \((?:failures|errors)=\d+(?:, (?:failures|errors)=\d+)*\)$',
                          output,flags=re.MULTILINE))


def tool(event,binding):
    run=Path(binding['run_dir']);journal=run/'hook-journal.json'
    ident=event.get('tool_use_id');command=(event.get('tool_input')or{}).get('command')
    if not isinstance(ident,str)or not isinstance(command,str):
        return {}
    with lock(run/'hook-journal.lock'):
        data=read(journal)or{'pending':{},'observations':[],'interventions':0,'model_calls':0}
        if len(data['observations'])>=2000:
            return {}  # Finite passive journal, never clears/resets goal state.
        source=digest(inventory(binding['repo'],exclude=IGNORE))
        if event['hook_event_name']=='PreToolUse':
            data['pending'][ident]={'before':source,'command':command,'at':time.time()}
            # Bound unmatched background/aborted calls separately.
            if len(data['pending'])>256:
                oldest=min(data['pending'],key=lambda k:data['pending'][k]['at']);del data['pending'][oldest]
            atomic_json(journal,data);return {}
        prior=data['pending'].pop(ident,None)
        if not prior:
            return {}
        code,output=response(event.get('tool_response'))
        signature=digest({'command':command,'before':prior['before'],'after':source,
                          'returncode':code,'output':stable_output(output)})
        record={'at':time.time(),'command':command,'before':prior['before'],'after':source,
                'returncode':code,'signature':signature,'output_tail':output[-2000:],
                'response_schema':shape(event.get('tool_response'))}
        previous=data['observations'][-1]if data['observations']else None
        observed_failure=(code is not None and code!=0)or test_failure(output)
        record['failure_evidence']='exit_code'if code is not None and code!=0 else'unittest_summary'if test_failure(output)else None
        stalled=bool(observed_failure and source==prior['before']and
                     previous and previous['signature']==signature)
        data['observations'].append(record)
        if stalled:data['interventions']+=1
        atomic_json(journal,data)
    if stalled:
        # PostToolUse block replaces an ALREADY EXECUTED result, not its action.
        reason=('GoalPilot observed the same failed command twice with identical inputs/source and output. '
                'It really ran both times. Diagnose the failing assertion or environment and change the hypothesis; '
                'do not repeat unchanged. Full journal: '+str(journal)+'\n'+output[-1200:])
        return {'decision':'block','reason':reason,'hookSpecificOutput':{'hookEventName':'PostToolUse','additionalContext':reason}}
    return {}


def handle(event):
    kind=event.get('hook_event_name');session_id=event.get('session_id')
    if kind not in ('PreToolUse','PostToolUse','Stop'):
        return {}
    # A beacon is capability evidence, never permission to change commands.
    if kind=='PreToolUse':
        atomic_json(root()/(key(session_id)+'.beacon.json'),
                    {'at':time.time(),'cwd':str(Path(event['cwd']).resolve()),'code_sha256':code_hash()})
    binding=active(event)
    if not binding:
        return {}
    if kind!='Stop':
        return tool(event,binding)
    from .session import finish
    begun=time.monotonic()
    result=finish(binding['run_dir'])
    record={'at':time.time(),'seconds':time.monotonic()-begun,'result':result,'stop_hook_active':event.get('stop_hook_active'),
            'engine_model_calls':0}
    with lock(Path(binding['run_dir'])/'hook-journal.lock'):
        path=Path(binding['run_dir'])/'stop-hooks.json';rows=read(path)or[];rows.append(record);atomic_json(path,rows)
    if result['closed']:
        retire(binding)
        return {'systemMessage':f"GoalPilot: {result['checks_passed']}/{result['checks_total']} frozen suites verified; no nested model call. Scope remains inferred."}
    if result['status'] in ('budget_exhausted','unsupported','verification_unavailable','integrity_failed'):
        retire(binding)
        return {'continue':False,'stopReason':'GoalPilot remains OPEN: '+json.dumps(result,ensure_ascii=False)}
    return {'decision':'block','reason':
            'GoalPilot acceptance failed. Continue the SAME original goal in THIS session; no other model/controller. '
            'Repair IMPLEMENTATION only, preserve the frozen tests/checks/deadline. End when the goal is fully implemented; '
            'the Stop hook runs the same acceptance again. Do not call finish separately.\n'+json.dumps(result,ensure_ascii=False)}


def main(argv=None):
    try:
        raw=sys.stdin.read(1048577)
        if len(raw)>1048576:raise ContractError('Hook input exceeds bound')
        event=json.loads(raw)
        if not isinstance(event,dict):raise ContractError('Hook input must be object')
        result=handle(event)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        # Never claim closure or request an extra model on an unavailable hook.
        result={'systemMessage':'GoalPilot hook unavailable; completion UNVERIFIED: '+str(exc)[:500]}
    print(json.dumps(result,ensure_ascii=False,separators=(',',':')))
    return 0
