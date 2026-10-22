"""Validate the frozen judge on correct complete platforms and isolated faults."""
from pathlib import Path
import tempfile
from concurrent.futures import ThreadPoolExecutor
from .cases import materialize
from .specs import SPECS
from .judge import evaluate
MUTANTS={
'flowdesk':[
 ('private-notes-leak','journey',[("if not c['internal']or role!='viewer'","if True")]),
 ('revision-not-advanced','isolation_or_revision',[("t['revision']+=1","t['revision']+=0")]),
 ('replay-is-live-ticket','idempotency',[("return old['result']","return w['tickets'][t['id']]")]),
 ('lease-boundary-delayed','recovery_or_returns',[("c['expires']>now","c['expires']>=now")]),
 ('tags-not-normalized','journey',[("return sorted(set(ident(t)for t in x))","return list(x)")]),
 ('restore-not-validated','backup',[("def validate_state(s):\n","def validate_state(s):\n    return\n")]),
],
'stockroom':[
 ('cancel-releases-shipped','recovery_or_returns',[("-=r['quantity']-sent.get((r['sku'],r['warehouse']),0)","-=r['quantity']")]),
 ('replay-not-original','idempotency',[("return old['result']","return {'on_hand':-1}")]),
 ('transfer-steals-reserved','isolation_or_revision',[("if q>left['on_hand']-left['reserved']:","if q>left['on_hand']:")]),
 ('return-over-history','recovery_or_returns',[("if r['quantity']>capacity.get(pair,0)-used.get(pair,0):","if r['quantity']>capacity.get(pair,0)-used.get(pair,0)+1:")]),
 ('warehouse-order-reversed','pagination_or_schedule',[("for wid in sorted(s['warehouses']):","for wid in sorted(s['warehouses'],reverse=True):")]),
 ('purchase-never-complete','journey',[("p['status']='received'if mapping(p['received'])==requested else'partial'","p['status']='partial'")]),
 ('restore-not-validated','backup',[("def validate_state(s):\n","def validate_state(s):\n    return\n")]),
],
'runforge':[
 ('expiry-boundary-inclusive','recovery_or_returns',[("now>=n['expires']","now>n['expires']")]),
 ('retry-delay-ignored','recovery_or_returns',[("n['not_before']=n['expires']+n['retry_delay']","n['not_before']=n['expires']")]),
 ('old-receipt-accepted','recovery_or_returns',[("or n.get('receipt')!=receipt "," ")]),
 ('catchup-order-reversed','pagination_or_schedule',[("selected=sorted(due)[:limit]","selected=sorted(due,reverse=True)[:limit]")]),
 ('run-revision-always-one','isolation_or_revision',[("'revision':w['revision'],'status':'active'","'revision':1,'status':'active'")]),
 ('artifact-size-is-characters','history_or_artifacts',[("len(content.encode())","len(content)")]),
 ('replay-is-live-run','idempotency',[("return s['keys'][key]['result']","return snapshot(s['runs'][rid])")]),
 ('restore-not-validated','backup',[("def validate_state(s):\n","def validate_state(s):\n    return\n")]),
]}


def _run_case(root,name):
    repo=materialize(root/name,name,True);correct=[]
    for seed in(90173,470117):correct.extend(evaluate(name,repo,seed))
    failures=[r for r in correct if not r['passed']]
    if failures:raise AssertionError((name,'Correct reference rejected',failures))
    original=(repo/'engine.py').read_text();mutants=[]
    for label,group,replacements in MUTANTS[name]:
        mutated=original
        for old,new in replacements:
            assert old in mutated,(name,label,old);mutated=mutated.replace(old,new)
        compile(mutated,label,'exec');(repo/'engine.py').write_text(mutated)
        rows=evaluate(name,repo,groups=[group]);assert not rows[0]['passed'],(name,'Fault not detected',label)
        mutants.append({'id':label,'group':group,'rejected':True})
    (repo/'engine.py').write_text(original)
    stub=materialize(root/(name+'-stub'),name);initial=evaluate(name,stub,groups=['public','journey'])
    assert not any(r['passed']for r in initial)
    return name,{'reference_groups_passed':len(correct),'initial_groups_failed':len(initial),'isolated_faults':mutants}


def run():
    with tempfile.TemporaryDirectory(prefix='goalpilot-ambitious-preflight-')as t:
        root=Path(t)
        # Each platform uses a distinct temporary workspace and only reads the
        # shared immutable specifications. Keep report order deterministic.
        with ThreadPoolExecutor(max_workers=3)as pool:
            return dict(pool.map(lambda name:_run_case(root,name),SPECS))
