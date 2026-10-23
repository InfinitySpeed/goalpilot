#!/usr/bin/env python3
"""Run the frozen helper-assisted engine profile with explicit host permissions."""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalpilot.autopilot import run_autopilot
from goalpilot.rpc import AppServerAdapter
from goalpilot.view import summarize
from goalpilot.model import ContractError

SCOPE = ('Read ONLY this repository, your current goal and its own evidence. Do not inspect other '
         'projects, research harnesses, judges, previous runs or sibling directories. No delegated models.\n\n')


class ProfileAdapter(AppServerAdapter):
    def __init__(self,*args,sandbox='workspace-write',**kwargs):
        if sandbox not in ('workspace-write','danger-full-access'):
            raise ValueError('Unsupported sandbox')
        self.sandbox=sandbox
        super().__init__(*args,**kwargs)

    def _request(self,method,params,deadline):
        if method=='thread/start':
            params={**params,'sandbox':self.sandbox}
        return super()._request(method,params,deadline)

    def execute(self,prompt,repo,timeout,log_dir,**kwargs):
        return super().execute(SCOPE+prompt,repo,timeout,log_dir,**kwargs)


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    goal=p.add_mutually_exclusive_group(required=True)
    goal.add_argument('--goal')
    goal.add_argument('--goal-file',type=Path)
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--sandbox',choices=('workspace-write','danger-full-access'),default='workspace-write',
                   help='Explicit Codex permissions; the recorded benchmark used danger-full-access.')
    p.add_argument('--model',default='gpt-6.1-sol')
    p.add_argument('--wall-seconds',type=float,default=600)
    p.add_argument('--max-calls',type=int,default=2)
    p.add_argument('--max-tokens',type=int,default=700000)
    p.add_argument('--max-uncached-tokens',type=int)
    return p


def main(argv=None):
    a=parser().parse_args(argv)
    try:
        goal=a.goal_file.read_text(encoding='utf-8')if a.goal_file else a.goal
        with ProfileAdapter(a.model,prepared=True,effort='low',sandbox=a.sandbox)as adapter:
            state=run_autopilot(goal,a.repo,a.run_dir,helpers=True,adapter=adapter,model=a.model,
                max_calls=a.max_calls,wall_seconds=a.wall_seconds,max_tokens=a.max_tokens,
                max_uncached_tokens=a.max_uncached_tokens)
    except (ContractError,OSError,ValueError) as exc:
        print('GoalPilot: '+str(exc),file=sys.stderr)
        return 2
    print(json.dumps(summarize(state),ensure_ascii=False,indent=2))
    return 0 if state['status']=='scope_passed'else 2


if __name__=='__main__':
    raise SystemExit(main())
