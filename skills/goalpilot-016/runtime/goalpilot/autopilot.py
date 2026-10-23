"""Direct-first autonomous execution: act, propose checks, verify, recover."""

from __future__ import annotations

import json
from pathlib import Path
import time

from .engine import atomic_json,lock,run_mission
from .model import ContractError,validate
from .rpc import AppServerAdapter


DELIVERY_SCHEMA={
    'type':'object','additionalProperties':False,
    'properties':{
        'summary':{'type':'string'},
        'assumptions':{'type':'array','items':{'type':'string'}},
        'limitations':{'type':'array','items':{'type':'string'}},
        'checks':{'type':'array','minItems':1,'maxItems':3,'items':{
            'type':'object','additionalProperties':False,
            'properties':{'id':{'type':'string'},'description':{'type':'string'},
                          'command':{'type':'array','items':{'type':'string'}},'timeout_seconds':{'type':'number'}},
            'required':['id','description','command','timeout_seconds']}}},
    'required':['summary','assumptions','limitations','checks']}

HELPER_DELIVERY_SCHEMA = {
    'type':'object','additionalProperties':False,
    'properties':{key:DELIVERY_SCHEMA['properties'][key] for key in ('summary','assumptions','limitations')},
    'required':['summary','assumptions','limitations']}


HELPER_GUIDANCE = """
The host supplied the exact verified portable helpers below. Do not edit them or copy their source.
For NEW pure apps with unspecified storage/backup format, prefer ReplayService: implement initial()
and PURE handle(state,operation,data), using self.opaque() for recorded IDs and explicit request times.
It already provides atomic storage, detached snapshots, locking, replay-validated restore and both real
transports. Keep ALL business/input guards in handle; use ServiceBase and a full validator for existing
formats. Prefer one concise flow(c) with exact business assertions and rejects(lambda:c(...));
self.assertJourney(flow) runs it directly, in real JSONL and HTTP, with separate fixture copies.
Dynamic IDs work naturally inside the flow. Add focused restore/corruption and race checks only as needed.
Implement every public rule, including idempotent replays under concurrent requests; do not weaken
tests or reinterpret required behavior to save tokens. Write implementation AND tests in ONE edit
call, then run one relevant suite; repair concrete failures without re-emitting unchanged code.
Use compact schema validation and direct transitions, avoiding duplicate flows and extra abstractions.
Aim for <=2500 emitted code/test tokens where feasible; correctness takes precedence. Preserve
customer data and existing complete documentation. Do not restate the README contract or append
usage already documented; edit docs only for missing or changed usage, in the same implementation edit.
Finish immediately after passing checks, with a one-sentence summary. The host verifies frozen tests.
"""


def initial_prompt(goal, *, helpers=False):
    if helpers:
        from .runtime_kit import API
        return f'''Complete this original coding goal autonomously in this repository:
{goal}

Implement EVERY public README workflow, return shape and business rule; preserve original tests/data.
Resolve reversible details yourself. Use the complete supplied context; read only missing, truncated,
changed or concretely needed files. Supplied imports are available: use them directly without
availability probes. No separate planning, broad sweeps, credentials, deployment or publication.
Finish after one relevant local suite and focused repairs. The host freezes and verifies the original
and delivered unittest suites; do not generate separate check commands or a second handoff file.
Return the compact final JSON schema with actual delivered behavior, assumptions and limitations.
''' + HELPER_GUIDANCE + '\n' + API
    prompt = f"""Complete this coding goal autonomously in the existing repository:
{goal}

Follow applicable repository instructions and README interfaces. Resolve reversible ambiguities yourself,
preserve existing user data, implement a complete end-to-end result and run meaningful local checks.
Inspect only instructions, contracts, and source/tests relevant to the goal; avoid broad repository sweeps
and generated, vendor, benchmark, or unrelated files.
Do not spend a separate session planning. Focus on the requested behavior; avoid unrelated features.
Do not deploy, publish, obtain credentials or perform destructive external actions.
Your final response must match the supplied JSON schema. Describe actual delivered behavior and limits.
Provide 1-3 bounded, local, non-destructive executable check commands that exercise the delivered user
behavior (including negative cases), preferably using the tests you have run. These commands run later
from repository cwd and must require no network, external credentials or deployment. Avoid file-existence
checks, no-op commands, test counts without behavioral assertions, or claims of success as evidence.
Keep this delivery report compact. You are proposing inferred checks, not proving subjective user satisfaction.
"""
    return prompt


def run_autopilot(goal, repo, run_dir, *, wall_seconds=600,max_calls=3,max_tokens=500000,model=None,checks=None,adapter=None,notify=None,max_uncached_tokens=None,helpers=False):
    start=time.monotonic()
    repo=Path(repo).resolve()
    run_dir=Path(run_dir).resolve()
    if not repo.is_dir():raise ContractError('Repository does not exist')
    if run_dir==repo or repo in run_dir.parents:raise ContractError('Evidence must live outside the agent repository')
    if not isinstance(goal,str) or not goal.strip():raise ContractError('Goal must not be empty')
    budget={'max_calls':max_calls,'wall_seconds':wall_seconds,'attempt_seconds':wall_seconds,'max_tokens':max_tokens}
    if max_uncached_tokens is not None:budget['max_uncached_tokens']=max_uncached_tokens
    # Validate budgets before starting a remote session, even before inferred checks exist.
    validate({'goal':goal,'repo':str(repo),'budget':budget,'checks':checks if checks is not None else [{'id':'bootstrap','description':'Temporary validation placeholder; never executed','command':['true']} ]})
    with lock(run_dir/'autopilot.lock'):
        if (run_dir/'state.json').exists() or (run_dir/'bootstrap-result.json').exists():
            raise ContractError('Run already started. Resume its mission rather than overwriting evidence.')
        original_gate = None
        receipts = []
        if helpers:
            if checks is not None:
                raise ContractError('Helper-assisted execution infers its checks; use helpers without explicit checks')
            from .support import validate_runtime, provision_runtime
            from .originals import capture
            from .gates import make_gate
            validate_runtime(repo)  # Fail collisions before any project write.
            original = capture(repo, run_dir/'originals', max_files=2000, max_bytes=64000000, max_entries=12000)
            if original['within_limits'] and not original['omitted']:
                original_gate = make_gate(repo, run_dir, original)
            if not original_gate:
                raise ContractError('Helper-assisted execution requires a bounded original unittest suite')
            receipts = provision_runtime(repo)
            atomic_json(run_dir/'helpers.json', receipts)
        owned=adapter is None
        adapter=adapter or AppServerAdapter(model,prepared=True,effort='low' if helpers else None)
        if helpers:
            adapter.known_helpers = {Path(r['path']).name: {'sha256':r['sha256'], 'bytes':Path(r['path']).stat().st_size} for r in receipts}
        try:
            if checks is not None:
                contract=validate({'goal':goal,'repo':str(repo),'scope':'user_defined','checks':checks,'budget':budget,
                                   'creation_mode':'direct-first','model':model})
                atomic_json(run_dir/'mission.json',contract)
                return run_mission(contract,adapter,run_dir,notify=notify)
            schema=run_dir/'delivery-schema.json'
            atomic_json(schema,HELPER_DELIVERY_SCHEMA if helpers else DELIVERY_SCHEMA)
            if notify:notify('Direct-first: implement and test in one session; no separate framing call')
            result=adapter.execute(initial_prompt(goal, helpers=helpers),repo,max(.001,wall_seconds-(time.monotonic()-start)-5),run_dir/'calls/1',schema=schema)
            atomic_json(run_dir/'bootstrap-result.json',result.to_dict())
            if result.returncode!=0:
                status='agent_unavailable' if result.fatal else 'incomplete'
                atomic_json(run_dir/'bootstrap-status.json',{'status':status,'reason':result.message[-2000:]})
                raise ContractError(f'Initial execution did not deliver a checkable report ({status}); evidence: {run_dir}')
            try:
                delivery=json.loads(result.message)
            except ValueError as exc:
                raise ContractError('Initial delivery is not valid JSON; evidence retained, no blind retry') from exc
            if not isinstance(delivery,dict):raise ContractError('Delivery must be an object')
            proposed_checks = [dict(original_gate['check'],id='gp-original-tests')] if helpers else delivery.get('checks')
            contract=validate({'goal':goal,'repo':str(repo),'scope':'inferred','checks':proposed_checks,
                'assumptions':delivery.get('assumptions',[]),'limitations':delivery.get('limitations',[]),
                'milestones':[],'budget':budget,'creation_mode':'direct-first','model':model})
            if helpers:
                from .engine import artifacts_intact
                if not artifacts_intact({'artifacts':receipts}):
                    raise ContractError('Provided helper changed; refusing verification')
                delivered = capture(repo, run_dir/'delivered-tests', max_files=2000, max_bytes=64000000, max_entries=12000)
                (run_dir/'delivered-gate').mkdir()
                delivered_gate = make_gate(repo, run_dir/'delivered-gate', delivered) if delivered['within_limits'] and not delivered['omitted'] else None
                if not delivered_gate:
                    raise ContractError('Delivered unittest suite cannot be frozen')
                contract['checks'] = [dict(original_gate['check'],id='gp-original-tests'),dict(delivered_gate['check'],id='gp-delivered-tests')]
                contract['artifacts'] = original_gate['artifacts'] + delivered_gate['artifacts'] + receipts
                contract['helper_assisted'] = True
            atomic_json(run_dir/'mission.json',contract)
            # The complete bootstrap time (context preparation and setup included)
            # remains charged to the persisted budget, including on later resume.
            seeded=result.to_dict()
            seeded['duration_seconds']=time.monotonic()-start
            return run_mission(contract,adapter,run_dir,notify=notify,
                seed_calls=[{'strategy':'implement','result':seeded}])
        finally:
            if owned:adapter.close()
