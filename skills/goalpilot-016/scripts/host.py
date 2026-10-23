#!/usr/bin/env python3
"""Run the shared local engine without inheriting another host's Codex hooks."""
import os
import argparse
import json
import subprocess
import tempfile
import math
from pathlib import Path
import runpy
import sys


def begin(args):
    parser=argparse.ArgumentParser(description='Save the exact goal and start a local session in one command.')
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--goal')
    source.add_argument('--goal-file',type=Path)
    parser.add_argument('--repo',required=True,type=Path)
    parser.add_argument('--run-dir',required=True,type=Path)
    parser.add_argument('--wall-seconds',type=float,default=900)
    parser.add_argument('--max-verifications',type=int,default=5)
    parser.add_argument('--max-tokens',type=int)
    parser.add_argument('--max-uncached-tokens',type=int)
    parser.add_argument('--helpers',action='store_true')
    parser.add_argument('--context',action='store_true')
    a=parser.parse_args(args);run=a.run_dir.absolute();repo=a.repo.resolve()
    if not repo.is_dir():raise ValueError('Repository directory does not exist')
    if not math.isfinite(a.wall_seconds)or a.wall_seconds<=0 or a.max_verifications<1:
        raise ValueError('Positive finite session budgets required')
    if any(v is not None and v<=0 for v in (a.max_tokens,a.max_uncached_tokens)):
        raise ValueError('Positive token budgets required')
    raw=a.goal_file.read_bytes()if a.goal_file is not None else (a.goal or '').encode('utf-8')
    goal=raw.decode('utf-8')
    if not goal.strip()or '\0'in goal:raise ValueError('Nonempty UTF-8 goal required')
    if any(p.is_symlink()for p in (run,*run.parents)):
        raise ValueError('Evidence path must not contain symlinks')
    if run==repo or repo in run.parents or run in repo.parents:
        raise ValueError('Evidence must be outside and separate from repository')
    if run.exists():
        # Accept a pre-created EMPTY container, never erase or reset session evidence.
        if not run.is_dir()or any(run.iterdir()):
            raise ValueError('Existing evidence preserved; use session status/finish, not a new begin')
        run.rmdir()
    if a.goal_file is None:
        if not a.goal or not a.goal.strip()or '\0'in a.goal:raise ValueError('Nonempty UTF-8 goal required')
        run.parent.mkdir(parents=True,exist_ok=True)
        descriptor,filename=tempfile.mkstemp(prefix=run.name+'-goal-',suffix='.txt',dir=run.parent)
        with os.fdopen(descriptor,'w',encoding='utf-8',newline='')as stream:stream.write(a.goal)
        goal_file=Path(filename)
    else:goal_file=a.goal_file
    command=[sys.executable,str(Path(__file__).with_name('goalpilot.py')),'session','start',
             '--goal-file',str(goal_file),'--repo',str(repo),'--run-dir',str(run),
             '--wall-seconds',str(a.wall_seconds),'--max-verifications',str(a.max_verifications)]
    for flag,value in (('--max-tokens',a.max_tokens),('--max-uncached-tokens',a.max_uncached_tokens)):
        if value is not None:command.extend([flag,str(value)])
    if a.helpers:command.append('--helpers')
    if a.context:command.append('--context')
    return subprocess.call(command)


def deliver(args):
    parser=argparse.ArgumentParser(description='Submit compact goal criteria and verify locally; no model calls.')
    parser.add_argument('run_dir',type=Path)
    parser.add_argument('--criteria-file',required=True,type=Path)
    a=parser.parse_args(args)
    data=json.loads(a.criteria_file.read_text(encoding='utf-8'))
    if not isinstance(data,dict):raise ValueError('Criteria document must be an object')
    items=data.get('criteria')
    if not isinstance(items,list)or not 1<=len(items)<=8:
        raise ValueError('Supply 1–8 explicit goal-derived criteria')
    criteria=[];requirements=[]
    for i,item in enumerate(items,1):
        if not isinstance(item,dict):raise ValueError('Criterion must be an object')
        quote=item['quote'];ident='c'+str(i)
        if not isinstance(quote,str)or not quote.strip():raise ValueError('Criterion needs a source quote')
        criterion={'id':ident,'statement':item.get('statement',quote),'source_quote':quote,
                   'check_ids':item.get('checks',['builder-tests'])}
        if 'blocker'in item:criterion['blocker']=item['blocker']
        criteria.append(criterion)
        requirements.append({'id':'r'+str(i),'statement':criterion['statement'],
                             'source_quote':quote,'criterion_ids':[ident]})
    handoff={'summary':data.get('summary','Verify submitted goal-derived criteria'),
             'assumptions':data.get('assumptions',[]),'limitations':data.get('limitations',[]),
             'checks':data.get('checks',[]),'criteria':criteria,'requirements':requirements}
    run=a.run_dir.absolute()
    # Existing session integrity is checked before creating a handoff or freezing anything.
    launcher=Path(__file__).with_name('goalpilot.py')
    check=subprocess.run([sys.executable,str(launcher),'session','status',str(run)],capture_output=True,text=True)
    if check.returncode:
        sys.stderr.write(check.stderr);return check.returncode
    completion_owner=json.loads(check.stdout).get('completion_owner')
    if (run/'acceptance.json').exists():
        raise ValueError('Acceptance already frozen; repair then use session finish without resubmitting')
    descriptor,filename=tempfile.mkstemp(prefix='delivery-handoff-',suffix='.json',dir=run)
    path=Path(filename)
    with os.fdopen(descriptor,'w',encoding='utf-8')as stream:json.dump(handoff,stream,ensure_ascii=False)
    submitted=subprocess.run([sys.executable,str(launcher),'session','submit',str(run),'--handoff',str(path)],capture_output=True,text=True)
    if submitted.returncode:
        sys.stderr.write(submitted.stderr+submitted.stdout);return submitted.returncode
    if completion_owner=='codex_stop_hook':
        sys.stdout.write(submitted.stdout)
        print('GoalPilot: acceptance frozen; end this session now. The configured Stop hook owns verification.')
        return 0
    return subprocess.call([sys.executable,str(launcher),'session','finish',str(run)])


def main():
    args = sys.argv[1:]
    os.environ.setdefault('PYTHONUTF8', '1')
    if os.name == 'nt' and not sys.flags.utf8_mode:
        os.execv(sys.executable, [sys.executable, '-X', 'utf8', str(Path(__file__).resolve()), *args])
    if not args or args[0] in ('--help', '-h'):
        print('GoalPilot local session adapter\n'
              'Usage: python3 host.py session {begin,deliver,start,check,finish,status,submit,verify,repair} ...\n'
              'No Codex executable, host hook setup or model calls are required.')
        return 0
    if args[0] != 'session':
        print('This adapter runs local session commands only. Use: host.py session --help', file=sys.stderr)
        return 2
    runtime_file=Path(__file__).resolve().parents[1]/'RUNTIME.json'
    runtime=json.loads(runtime_file.read_text())if runtime_file.exists()else{}
    if runtime.get('host')!='codex'or os.name=='nt':
        os.environ.pop('CODEX_THREAD_ID', None)
    if len(args)>1 and args[0]=='session'and args[1]in ('begin','deliver'):
        try:return (begin if args[1]=='begin'else deliver)(args[2:])
        except (OSError,ValueError,KeyError,TypeError)as exc:
            print('GoalPilot delivery: '+str(exc),file=sys.stderr);return 2
    launcher = Path(__file__).resolve().with_name('goalpilot.py')
    sys.argv = [str(launcher), *args]
    runpy.run_path(str(launcher), run_name='__main__')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
