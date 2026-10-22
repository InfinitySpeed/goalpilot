"""One live smoke test with production defaults; not a comparative benchmark."""

import argparse
import json
from pathlib import Path
import time

from goalpilot.adapters import CodexAdapter
from goalpilot.benchmark import fixtures
from goalpilot.cli import initialize
from goalpilot.engine import atomic_json, run_mission, token_totals, verify
from goalpilot.model import ContractError, digest
from .holdouts import holdouts
from .vague_goal import GOAL, README


def run(args):
    if not args.live:
        raise ContractError("--live required; uses real Codex usage")
    root=args.output.resolve()
    if root.exists() and any(root.iterdir()):
        raise ContractError("Output must be new or empty")
    repo=root/'repo'
    repo.mkdir(parents=True)
    (repo/'notes.py').write_text("import json\nprint(json.dumps([]))\n")
    (repo/'README.md').write_text(README)
    acceptance=fixtures()[0]['checks']+holdouts()['notes']
    atomic_json(root/'manifest.json',{'kind':'live_default_configuration_smoke','goal':GOAL,
        'acceptance':acceptance,'acceptance_hash':digest(acceptance),
        'budget':{'max_calls':4,'wall_seconds':600,'attempt_seconds':180,'max_tokens':100000,'planning_seconds':90},
        'note':'Single default-config integration check, separate from the paired experiments. Reuses the notes task; not an additional independent efficacy observation.'})
    options=argparse.Namespace(goal=GOAL,repo=repo,output=root/'mission.json',checks=None,model=None,
        max_calls=4,wall_seconds=600,attempt_seconds=180,max_tokens=100000,planning_seconds=90)
    start=time.monotonic()
    try:
        contract=initialize(options)
    except ContractError as exc:
        result=json.loads((root/'mission-planning/result.json').read_text())
        status='planning_failed'
        calls=[{'strategy':'planning','result':result}]
        atomic_json(root/'failure.json',{'error':str(exc)})
    else:
        state=run_mission(contract,CodexAdapter(),root/'run',notify=lambda x:print(x,flush=True))
        status=state['status']
        calls=state['calls']
    execution_seconds=time.monotonic()-start
    judge={'goal':GOAL,'repo':str(repo),'checks':acceptance}
    assessment_start=time.monotonic()
    evidence=verify(judge,assessment_start+30,root/'external-evidence')
    report={'kind':'live_default_configuration_smoke','simulated':False,'internal_status':status,
        'external_goal_success':all(x['passed'] for x in evidence),
        'checks_passed':sum(x['passed'] for x in evidence),'checks_total':len(evidence),
        'execution_seconds_including_planning':execution_seconds,
        'assessment_seconds':time.monotonic()-assessment_start,'agent_calls':len(calls),
        'usage':token_totals(calls),'checks':evidence,
        'interpretation':'Integration smoke test only. Does not establish a benefit over direct Codex.'}
    atomic_json(root/'report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False,indent=2),flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args())
