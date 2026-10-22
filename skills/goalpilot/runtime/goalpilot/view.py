"""Read-only live mission status without dumping source or full model reports."""
import json
from pathlib import Path
import time
from .engine import token_totals
from .metrics import summarize


def status(run_dir):
    run_dir=Path(run_dir);path=run_dir/'state.json'
    if path.exists():
        state=json.loads(path.read_text());out=summarize(state)
        pending=state.get('pending')
        active=state['active_seconds']
        if pending:active+=min(pending['reserved_seconds'],max(0,time.time()-pending['started_at']))
        out['active_seconds_estimate']=active
        out['remaining_seconds_estimate']=max(0,state['contract']['budget']['wall_seconds']-active)
        checks=state['verifications'][-1]['checks'] if state['verifications'] else []
        out['remaining_checks']=[{'id':c['id'],'output':c['output'][-1200:]} for c in checks if not c['passed']]
        return out
    flow=json.loads((run_dir/'finish-run.json').read_text());budget=flow['config']['budget']
    active=flow['active_seconds'];pending=flow.get('pending')
    if pending:
        used=min(pending['reserved_seconds'],max(0,time.time()-pending['started_at']))
        active=max(active,pending['started_active_seconds']+used)
    return {'goal':flow['config']['goal'],'phase':flow['phase'],'status':flow['status'],
        'agent_calls':len(flow['calls']),'max_calls':budget['max_calls'],
        'active_seconds_estimate':active,'remaining_seconds_estimate':max(0,budget['wall_seconds']-active),
        'usage':token_totals(flow['calls']),'pending_call':flow['calls'][pending['index']]['strategy'] if pending else None,
        'last_error':flow.get('error'),
        'note':'Usage may still be missing for an active/interrupted call. Time is a live estimate.'}
