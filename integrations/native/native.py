#!/usr/bin/env python3
"""Explicit native checks with frozen tests, bounded evidence and no model calls."""
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

IGNORE={'.git','.hg','.svn','node_modules','__pycache__','.pytest_cache','.mypy_cache','.venv','venv','dist','build','target','.agents','.claude'}
MAX_BYTES=32_000_000
MAX_FILES=3000

def digest(data): return hashlib.sha256(data).hexdigest()
def put(path,value):
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)
def read(path): return json.loads(path.read_text(encoding='utf-8'))
def inventory(repo):
    rows={};size=0
    for root,dirs,names in os.walk(repo,followlinks=False):
        dirs[:]=sorted(d for d in dirs if d not in IGNORE)
        for d in dirs:
            if (Path(root)/d).is_symlink(): raise ValueError('Unsupported source symlink: '+str(Path(root)/d))
        for name in sorted(names):
            p=Path(root)/name;rel=p.relative_to(repo).as_posix()
            if name=='.env' or name.startswith('.env.') or p.suffix.lower()in('.pem','.key') or name in ('auth.json','credentials.json'):continue
            if p.is_symlink():raise ValueError('Unsupported source symlink: '+rel)
            size+=p.stat().st_size
            if size>MAX_BYTES or len(rows)>=MAX_FILES or p.stat().st_size>4_000_000:raise ValueError('Unsupported repository size; narrow the repository explicitly')
            rows[rel]=digest(p.read_bytes())
    return rows

def is_test(name,expanded=True):
    p=Path(name);base=p.name.lower()
    if expanded and p.suffix.lower()in('.java','.cs')and re.search(r'(^Test[A-Z]|Tests?\.|Spec\.)',p.name):return True
    if expanded and any(x.lower().endswith('.tests')for x in p.parts[:-1]):return True
    return any(x.lower()in('test','tests','__tests__','spec','specs','fixtures','testdata')for x in p.parts[:-1]) or bool(re.search(r'(^test[_.-]|[_.-](test|spec)[_.-]|_test\.|^conftest\.py$)',base))

def test_names(files,paths=(),expanded=True):
    return {n:sha for n,sha in files.items()if is_test(n,expanded)or any(n==p or n.startswith(p+'/')for p in paths)}

def copy_files(repo,dest,files):
    for name in files:
        p=dest/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,p)

def seal(run,name,value):
    put(run/name,value);(run/(name+'.sha256')).write_text(digest((run/name).read_bytes()))
def sealed(run,name):
    if digest((run/name).read_bytes())!=(run/(name+'.sha256')).read_text():raise ValueError('Frozen evidence changed: '+name)
    return read(run/name)
def load(run):
    if run.is_symlink():raise ValueError('Symlink evidence refused')
    c=sealed(run,'session.json')
    if digest((run/'goal.bin').read_bytes())!=c['goal_sha256']:raise ValueError('Original goal changed')
    for name,sha in c['original'].items():
        if digest((run/'original'/name).read_bytes())!=sha:raise ValueError('Original snapshot changed: '+name)
    state=sealed(run,'state.json')
    if(run/'acceptance.json').exists():
        ac=sealed(run,'acceptance.json')
        snapshots=[{'files':ac['tests'],'directory':'builder-tests'},*state.get('test_revisions',[])]
        for snapshot in snapshots:
            for name,value in snapshot['files'].items():
                p=run/snapshot['directory']/name
                if p.is_symlink()or digest(p.read_bytes())!=value:raise ValueError('Frozen test snapshot changed: '+name)
        if(run/'accepted-tests.json').exists():
            accepted=sealed(run,'accepted-tests.json')
            if not any(accepted==x for x in snapshots):raise ValueError('Unknown accepted test snapshot')
    return c,state
def elapsed(c):return max(0,time.time()-c['started'])
def report(run,c,s):
    stale=s.get('verified_source') is not None and inventory(Path(c['repo']))!=s['verified_source']
    result={k:v for k,v in s.items()if k not in ('verified_source','attempts')}
    result['attempts']=len(s['attempts'])
    result['test_revisions']=len(s.get('test_revisions',[]))
    latest=s['attempts'][-1]if s['attempts']else{}
    result['checks_passed']=sum(row['passed']for row in latest.get('checks',[]))
    result['checks_total']=len(latest.get('checks',[]))
    result['criteria']=[{'id':'c'+str(n),'status':i['status'],**({'quote':i['quote'],'blocker':i.get('blocker','')}if i['status']!='verified'else{})}for n,i in enumerate(latest.get('criteria',[]),1)]
    result['evidence']=str(run)
    result['next_action']='stop'if s.get('goal_complete')and not stale else'implement'if not s['attempts']else'repair_source_or_justify_builder_draft_revision'
    if latest and not stale and all(row['passed']for row in latest.get('checks',[]))and any(i['status']=='blocked'for i in latest.get('criteria',[])):result['next_action']='stop_blocked'
    failures=[]
    for row in latest.get('checks',[]):
        if row['passed']:continue
        item=dict(row);path=run/('attempt-'+str(len(s['attempts'])))/(row['suite']+'-'+str([c['id']for c in sealed(run,'acceptance.json')['checks']].index(row['id']))+'.log')
        if path.exists():
            with path.open('rb')as stream:
                stream.seek(max(0,path.stat().st_size-4096))
                item['output_tail']=stream.read(4096).decode('utf-8',errors='replace')
        failures.append(item)
    result['failed_checks']=failures
    result.update(elapsed_seconds=round(elapsed(c),3),remaining_seconds=max(0,round(c['wall_seconds']-elapsed(c),3)),engine_model_calls=0,caller_usage='UNKNOWN',stale=stale,goal_complete=bool(s.get('goal_complete')and not stale))
    if stale and s['status']in('verified','incomplete'):result['status']='stale'
    return result

def service_scaffold(repo):
    """Only opt compatible, unimplemented stdlib transport scaffolds into helpers."""
    readme=repo/'README.md';app=repo/'app.py'
    if not readme.is_file()or not app.is_file()or readme.is_symlink()or app.is_symlink():return False
    with readme.open(encoding='utf-8')as stream:text=stream.read(64000).lower()
    if not all(x in text for x in ('jsonl','http','app.service')):return False
    try:
        with app.open(encoding='utf-8')as stream:tree=ast.parse(stream.read(64000))
    except (SyntaxError,UnicodeError):return False
    classes=[n for n in tree.body if isinstance(n,ast.ClassDef)and n.name=='Service']
    if len(classes)!=1:return False
    methods={n.name:n for n in classes[0].body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    if set(methods)-{'__init__','call'}or'call'not in methods:return False
    body=methods['call'].body
    if len(body)!=1 or not isinstance(body[0],ast.Raise):return False
    error=body[0].exc
    stub=isinstance(error,ast.Call)and isinstance(error.func,ast.Name)and(error.func.id=='NotImplementedError'or any(isinstance(x,ast.Constant)and isinstance(x.value,str)and'not implemented'in x.value.lower()for x in error.args))
    if not stub:return False
    init=methods.get('__init__')
    if init and any(not isinstance(n,ast.Pass)and not(isinstance(n,ast.Assign)and isinstance(n.value,(ast.Name,ast.Constant)))for n in init.body):return False
    return any('unittest'in f.read_text(encoding='utf-8')for f in (repo/'tests').glob('test*.py')if f.is_file()and not f.is_symlink())

def legacy_command(run,command,criteria=None):
    argv=[sys.executable,str(Path(__file__).with_name('host.py')),'session',command,str(run)]
    if criteria:argv+=['--criteria-file',str(criteria)]
    return subprocess.call(argv)

def begin(a):
    repo=a.repo.resolve();run=a.run_dir.absolute()
    if not repo.is_dir():raise ValueError('Repository required')
    if any(p.is_symlink()for p in(run,*run.parents))or repo==run or repo in run.parents or run in repo.parents:raise ValueError('Evidence must be separate, outside the repository, without symlinks')
    if run.exists():raise ValueError('Existing evidence preserved: use status/finish')
    if not math.isfinite(a.wall_seconds)or a.wall_seconds<=0 or a.max_verifications<1:raise ValueError('Positive finite budgets required')
    raw=a.goal_file.read_bytes()if a.goal_file else a.goal.encode('utf-8');goal=raw.decode('utf-8')
    if not goal.strip()or '\0'in goal:raise ValueError('Nonempty UTF-8 goal required')
    if a.mode=='service'or a.mode=='auto'and service_scaffold(repo):
        argv=[sys.executable,str(Path(__file__).with_name('host.py')),'session','begin','--repo',str(repo),'--run-dir',str(run),'--wall-seconds',str(a.wall_seconds),'--max-verifications',str(a.max_verifications),'--helpers']
        argv+=['--goal-file',str(a.goal_file)]if a.goal_file else['--goal',a.goal]
        if a.context:argv.append('--context')
        result=subprocess.run(argv,capture_output=True,text=True)
        sys.stdout.write(result.stdout);sys.stderr.write(result.stderr)
        if result.returncode==0 and a.context:
            service=Path(__file__).resolve().parents[1]/'references/service.md'
            body=service.read_text(encoding='utf-8')
            print('SERVICE MODE ALREADY STARTED. Do NOT begin again. Follow this exact optimized protocol from Execution discipline onward. GP = '+str(Path(__file__).with_name('host.py').resolve()))
            print(body[body.index('Execution discipline:'):])
        return result.returncode
    started=time.time();files=inventory(repo);run.mkdir(parents=True)
    (run/'goal.bin').write_bytes(raw);copy_files(repo,run/'original',files)
    c={'repo':str(repo),'goal_sha256':digest(raw),'original':files,'started':started,'wall_seconds':a.wall_seconds,'max_verifications':a.max_verifications}
    seal(run,'session.json',c)
    s={'status':'ready','attempts':[],'goal_complete':False};seal(run,'state.json',s)
    print(json.dumps(report(run,c,s)))
    if a.context:
        print('Original goal preserved verbatim in goal.bin. INITIAL CONTEXT (bounded; read missing details only):')
        selected=sorted(files,key=lambda n:(Path(n).name not in ('AGENTS.md','README.md','package.json','pyproject.toml','Makefile','Cargo.toml','go.mod'),n))
        used=0
        for name in selected:
            if used>=18000:break
            raw=(repo/name).read_bytes()
            try:text=raw.decode('utf-8')
            except UnicodeDecodeError:continue
            room=18000-used-len(name)-40
            if room<=0:break
            limit=min(len(text),6000,room)
            fragment=f'FILE {name} complete={limit==len(text)}\n'+text[:limit]
            used+=len(fragment)+1;print(fragment)
        listing=', '.join(files)
        print('FILES: '+listing[:4096]+(' ... [truncated: use rg --files for named missing paths]'if len(listing)>4096 else''))
        print('DELIVERY: Quote every goal clause in 1–8 criteria. Example: '+json.dumps({'checks':[{'id':'tests','argv':['python3','check.py']}],'criteria':[{'quote':'EXACT GOAL PHRASE','checks':['tests']}]}))
        print('Use the documented full project check runner plus focused behavior tests; never assume a bare compiler command exists or replace/skip original tests. In this SAME implementation command save criteria and run: '+sys.executable+' '+str(Path(__file__).resolve())+' deliver '+str(run)+' --criteria-file CRITERIA')
        print('Use checks:[] plus a blocker for unverifiable scope. Keep accepted tests immutable; correct a draft only before its first green run and with a specification-based reason. On goal_complete:true stop immediately: no status/finish rerun. Preserve all goal clauses; authored tests are not independent semantic proof.')
    return 0

def acceptance(run,c,data):
    checks=data.get('checks',[]);criteria=data.get('criteria',[])
    if not isinstance(checks,list)or len(checks)>16 or not isinstance(criteria,list)or not 1<=len(criteria)<=8:raise ValueError('Expected 1–8 criteria and <=16 checks')
    paths=data.get('test_paths',[])
    if not isinstance(paths,list)or any(not isinstance(p,str)or not p or '\\'in p or Path(p).is_absolute()or '..'in Path(p).parts or p!=Path(p).as_posix()for p in paths):raise ValueError('test_paths must be relative files or directories')
    ids=[]
    for check in checks:
        ident=check.get('id');argv=check.get('argv')
        if not isinstance(ident,str)or not ident.strip()or ident in ids or not isinstance(argv,list)or not argv or any(not isinstance(v,str)or '\0'in v for v in argv):raise ValueError('Unique check IDs and nonempty argv lists required')
        cwd=check.get('cwd','.')
        if not isinstance(cwd,str)or not cwd or '\\'in cwd or Path(cwd).is_absolute()or '..'in Path(cwd).parts:raise ValueError('Check cwd must stay inside repository')
        if not(Path(c['repo'])/cwd).is_dir():raise ValueError('Check cwd must exist')
        ids.append(ident)
    goal=(run/'goal.bin').read_bytes().decode('utf-8')
    for item in criteria:
        quote=item.get('quote');links=item.get('checks');blocker=item.get('blocker','')
        if not isinstance(quote,str)or not quote.strip()or quote not in goal:raise ValueError('Criterion must quote the original goal')
        if not isinstance(links,list)or any(x not in ids for x in links)or len(set(links))!=len(links)or not isinstance(blocker,str)or not links and not blocker.strip():raise ValueError('Criterion needs valid checks or an explicit blocker')
    if set(ids)!={x for i in criteria for x in i['checks']}:raise ValueError('Every check must support a criterion')
    repo=Path(c['repo']);files=inventory(repo);tests=test_names(files,paths)
    if any(not any(n==p or n.startswith(p+'/')for n in set(files)|set(c['original']))for p in paths):raise ValueError('test_paths must match captured files')
    copy_files(repo,run/'builder-tests',tests)
    result={'checks':checks,'criteria':criteria,'tests':tests,'test_paths':paths}
    seal(run,'acceptance.json',result)
    return result

def verify(run,c,s,revision=None):
    ac=sealed(run,'acceptance.json');repo=Path(c['repo'])
    snapshots=[{'files':ac['tests'],'directory':'builder-tests'},*s.get('test_revisions',[])]
    for snapshot in snapshots:
        for name,sha in snapshot['files'].items():
            if digest((run/snapshot['directory']/name).read_bytes())!=sha:raise ValueError('Frozen builder snapshot changed: '+name)
    accepted=sealed(run,'accepted-tests.json')if(run/'accepted-tests.json').exists()else None
    if accepted and not any(accepted==x for x in snapshots):raise ValueError('Unknown accepted test snapshot')
    active=accepted or snapshots[-1]
    source=inventory(repo);current=test_names(source,ac.get('test_paths',[]),expanded='test_paths'in ac)
    if accepted and current!=active['files']:raise ValueError('Accepted tests are frozen; restore them before repairing source')
    if s.get('verified_source')==source and (s.get('goal_complete')or s.get('attempts')and all(r['passed']for r in s['attempts'][-1]['checks'])and any(i['status']=='blocked'for i in s['attempts'][-1]['criteria'])):
        print(json.dumps(report(run,c,s),ensure_ascii=False));return 0 if s.get('goal_complete')else 1
    if elapsed(c)>=c['wall_seconds'] or len(s['attempts'])>=c['max_verifications']:
        s.update(status='budget_exhausted',goal_complete=False);seal(run,'state.json',s);print(json.dumps(report(run,c,s)));return 1
    if current!=active['files']:
        if not revision or not revision.strip():
            s.update(status='test_revision_required',goal_complete=False);seal(run,'state.json',s)
            result=report(run,c,s);result['next_action']='finish --test-revision SPECIFICATION_BASED_REASON; keep originals/criteria/checks and every previous draft'
            print(json.dumps(result));return 1
        if len(revision)>2000 or not set(active['files']).issubset(current):raise ValueError('Revision needs a concise rationale and must retain every previous test file')
        folder='test-revisions/'+str(len(s.get('test_revisions',[]))+1)
        if(run/folder).exists():raise ValueError('Existing test revision preserved')
        copy_files(repo,run/folder,current)
        active={'files':current,'directory':folder,'reason':revision.strip()}
        s.setdefault('test_revisions',[]).append(active);seal(run,'state.json',s)
    test_files=active['files'];test_folder=run/active['directory']
    rows=[];attempt=run/f'attempt-{len(s["attempts"])+1}';attempt.mkdir()
    original_tests=test_names(c['original'],ac.get('test_paths',[]),expanded='test_paths'in ac)
    # Builder includes every byte-identical original test: run their union once.
    # Changed/deleted originals still run separately from their frozen copies.
    suites=[('builder',test_files,test_folder)]
    if original_tests and any(test_files.get(n)!=sha for n,sha in original_tests.items()):suites.insert(0,('original',original_tests,run/'original'))
    for label,tests,frozen in suites:
        with tempfile.TemporaryDirectory(prefix='goalpilot-native-')as tmp:
            work=Path(tmp);copy_files(repo,work,source)
            for name in source:
                if name in current and name not in test_files:(work/name).unlink()
            copy_files(test_folder,work,test_files)
            copy_files(frozen,work,tests)
            # Reuse installed dependencies without copying or installing them.
            for name in ('node_modules','.venv','venv'):
                p=repo/name
                if p.is_dir():
                    try:(work/name).symlink_to(p,target_is_directory=True)
                    except OSError:raise ValueError('Dependency linking unsupported on this host')
            for check in ac['checks']:
                remaining=c['wall_seconds']-elapsed(c);row={'suite':label,'id':check['id'],'passed':False,'blocked':False}
                log=attempt/(label+'-'+str(ac['checks'].index(check))+'.log');start=time.monotonic()
                if remaining<=0:row.update(blocked=True,error='deadline')
                else:
                    try:
                        # File-backed output avoids unbounded pipe memory; kill whole POSIX group on timeout.
                        with log.open('wb')as stream:
                            proc=subprocess.Popen(check['argv'],cwd=work/check.get('cwd','.'),stdout=stream,stderr=subprocess.STDOUT,start_new_session=os.name!='nt')
                            try:code=proc.wait(timeout=remaining)
                            except subprocess.TimeoutExpired:
                                if os.name!='nt':
                                    import signal
                                    os.killpg(proc.pid,signal.SIGKILL)
                                else:subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);proc.kill()
                                proc.wait();raise
                        row.update(returncode=code,passed=code==0)
                    except (OSError,subprocess.TimeoutExpired)as exc:row.update(blocked=True,error=str(exc))
                row['seconds']=time.monotonic()-start;rows.append(row)
    changed=inventory(repo)!=source
    criteria=[]
    for item in ac['criteria']:
        evidence=[r for r in rows if r['id']in item['checks']]
        status='blocked'if item.get('blocker')or any(r['blocked']for r in evidence)else'verified'if evidence and all(r['passed']for r in evidence)and not changed else'missing'
        criteria.append({**item,'status':status})
    complete=all(i['status']=='verified'for i in criteria)and not changed and elapsed(c)<c['wall_seconds']
    record={'test_snapshot':active['directory'],'checks':rows,'criteria':criteria,'source_changed_during_checks':changed};put(attempt/'result.json',record)
    if complete and not accepted:seal(run,'accepted-tests.json',active)
    s['attempts'].append(record);s.update(status='verified'if complete else'incomplete',goal_complete=complete,verified_source=source)
    seal(run,'state.json',s);print(json.dumps(report(run,c,s),ensure_ascii=False));return 0 if complete else 1

def main():
    os.environ.setdefault('PYTHONUTF8','1')
    if os.name=='nt'and not sys.flags.utf8_mode:os.execv(sys.executable,[sys.executable,'-X','utf8',str(Path(__file__).resolve()),*sys.argv[1:]])
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('begin');p.add_argument('--repo',type=Path,required=True);p.add_argument('--run-dir',type=Path,required=True)
    group=p.add_mutually_exclusive_group(required=True);group.add_argument('--goal');group.add_argument('--goal-file',type=Path)
    p.add_argument('--mode',choices=('auto','native','service'),default='auto');p.add_argument('--wall-seconds',type=float,default=900);p.add_argument('--max-verifications',type=int,default=5);p.add_argument('--context',action='store_true')
    for name in ('deliver','finish','status'):
        p=sub.add_parser(name);p.add_argument('run_dir',type=Path)
        if name=='deliver':p.add_argument('--criteria-file',type=Path,required=True)
        if name=='finish':p.add_argument('--test-revision')
    args=sys.argv[1:]
    if args and args[0]=='session':args=args[1:]
    a=parser.parse_args(args)
    try:
        if a.command=='begin':return begin(a)
        run=a.run_dir.absolute()
        if (run/'session-state.json').exists():
            if getattr(a,'test_revision',None):raise ValueError('Test-draft revisions apply to native sessions only; the specialized engine keeps its original frozen acceptance')
            return legacy_command(run,a.command,getattr(a,'criteria_file',None))
        c,s=load(run)
        if a.command=='status':print(json.dumps(report(run,c,s),ensure_ascii=False));return 0
        if a.command=='deliver':
            if(run/'acceptance.json').exists():raise ValueError('Acceptance frozen: repair then finish')
            acceptance(run,c,read(a.criteria_file))
        return verify(run,c,s,getattr(a,'test_revision',None))
    except (OSError,ValueError,KeyError,TypeError)as exc:
        print(json.dumps({'status':'blocked','goal_complete':False,'error':str(exc)}));return 2

if __name__=='__main__':raise SystemExit(main())
