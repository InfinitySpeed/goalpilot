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

def validate_pytest_node_args(check,repo):
    """Reject misspelled static Python test nodes before they consume a verification."""
    root=Path(repo).resolve();working=(root/check.get('cwd','.')).resolve()
    for arg in check['argv']:
        if '::' not in arg:continue
        filename,*nodes=arg.split('::')
        if not filename.endswith('.py')or not nodes:continue
        path=Path(filename)
        if not path.is_absolute():path=working/path
        try:path=path.resolve();path.relative_to(root);tree=ast.parse(path.read_text(encoding='utf-8'))
        except (OSError,ValueError,UnicodeError,SyntaxError):continue
        valid=set()
        def visit(items,parents=()):
            for item in items:
                if isinstance(item,ast.ClassDef):visit(item.body,parents+(item.name,))
                elif isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef)) and item.name.startswith('test'):
                    valid.add('::'.join(parents+(item.name,)))
        visit(tree.body)
        selected='::'.join(n.split('[',1)[0]for n in nodes)
        if selected not in valid:raise ValueError('Unknown pytest node; check the exact test name before freezing acceptance: '+arg)

def pytest_nodes_exist_in_snapshot(check,repo,snapshot,files):
    """Whether every explicit pytest node existed in the frozen test snapshot."""
    root=Path(repo).resolve();working=Path(check.get('cwd','.'));found=False
    for arg in check['argv']:
        if '::' not in arg:continue
        filename,*nodes=arg.split('::')
        if not filename.endswith('.py')or not nodes:continue
        found=True;path=Path(filename)
        try:name=path.resolve().relative_to(root).as_posix() if path.is_absolute() else (working/path).as_posix()
        except ValueError:return False
        if name not in files:return False
        try:tree=ast.parse((Path(snapshot)/name).read_text(encoding='utf-8'))
        except (OSError,UnicodeError,SyntaxError):return False
        valid=set()
        def visit(items,parents=()):
            for item in items:
                if isinstance(item,ast.ClassDef):visit(item.body,parents+(item.name,))
                elif isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef)) and item.name.startswith('test'):
                    valid.add('::'.join(parents+(item.name,)))
        visit(tree.body)
        if '::'.join(n.split('[',1)[0]for n in nodes)not in valid:return False
    return True if found else None

def declared_test_ids(path):
    """Conservatively preserve named test cases when a contract supersedes a test file."""
    try:text=path.read_text(encoding='utf-8')
    except (OSError,UnicodeError):return set()
    # Python tests are the common case. The second form covers conventional Java/JUnit
    # methods; unknown test formats remain auditable but cannot claim name preservation.
    found=set(re.findall(r'^\s*(?:async\s+)?def\s+(test\w+)\s*\(',text,re.M))
    found.update(re.findall(r'^\s*(?:public\s+)?(?:void|fun)\s+(test\w+)\s*\(',text,re.M))
    return found

def validate_superseded(repo,original_root,original,active,paths):
    if not isinstance(paths,list)or len(set(paths))!=len(paths):raise ValueError('supersede_tests must be a unique list of test files')
    changed={n for n in original if original[n]!=active.get(n)}
    for name in paths:
        if not isinstance(name,str)or name not in changed or not is_test(name):raise ValueError('Only changed original test files may be explicitly superseded: '+str(name))
        old_names=declared_test_ids(Path(original_root)/name)
        current_names=declared_test_ids(Path(repo)/name)
        # Keep every named case; only its obsolete assertions may change. The original
        # bytes remain sealed in evidence and all revised cases run from the builder copy.
        if not old_names or not old_names.issubset(current_names):raise ValueError('Superseded file must retain every named test case: '+name)
    return set(paths)

def test_file_is_additive(original_root,builder_root,name):
    """True only when the revised file preserves every original byte as a prefix."""
    old=Path(original_root)/name;new=Path(builder_root)/name
    if old.suffix.lower() not in ('.py','.pyi') or not old.is_file() or not new.is_file():return False
    try:return new.read_bytes().startswith(old.read_bytes())
    except OSError:return False

def pytest_failure_ids(path):
    try:lines=Path(path).read_text(encoding='utf-8',errors='replace').splitlines()
    except OSError:return set()
    found=set()
    for line in lines:
        match=re.match(r'^(?:FAILED|ERROR)\s+(.+?)(?:\s+-\s+.*)?$',line)
        if match:found.add(match.group(1).strip())
    return found

def pytest_failure_files(path,repo,cwd='.'):
    root=Path(repo).resolve();base=(root/cwd).resolve();found=set()
    for node in pytest_failure_ids(path):
        rel=node.split('::',1)[0]
        candidate=(base/rel).resolve()
        try:candidate.relative_to(root)
        except ValueError:continue
        if candidate.is_file():found.add(candidate.relative_to(base).as_posix())
    return sorted(found)

def selective_pytest_command(argv,files):
    """Limit a baseline rerun to failing test files when pytest selection is simple."""
    if not files:return None
    index=next((i for i,arg in enumerate(argv)if Path(arg).name=='pytest'),None)
    if index is None:return None
    # Preserve quiet/verbosity flags; selection, config, plugin, or cwd options can
    # change what a baseline run means, so those conservatively use the full command.
    tail=argv[index+1:]
    if any(arg not in ('-q','-qq','-v','-vv','--quiet','--verbose')for arg in tail):return None
    return [*argv[:index+1],'-q',*files]

def is_focused_check(argv):
    return any(a=='-k'or a.startswith('-k=')or '::'in a or is_test(a,expanded=True) for a in argv)

def changed_pytest_nodes(original_root,original_tests,current_root,current_tests):
    """Names of added/edited Python test functions; unknown formats are conservative."""
    changed=set()
    def nodes(root,name):
        p=Path(root)/name
        try:tree=ast.parse(p.read_text(encoding='utf-8'))
        except (OSError,UnicodeError,SyntaxError):return None
        found={}
        def visit(items,parents=()):
            for item in items:
                if isinstance(item,ast.ClassDef):visit(item.body,parents+(item.name,))
                elif isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef)) and item.name.startswith('test'):
                    ident='::'.join(parents+(item.name,))
                    found[ident]=ast.dump(item,include_attributes=False)
        visit(tree.body);return found
    for name in set(original_tests)|set(current_tests):
        if not name.endswith('.py'):continue
        old=nodes(original_root,name) if name in original_tests else {}
        new=nodes(current_root,name) if name in current_tests else {}
        if old is None or new is None:
            changed.add(name+'::');continue
        changed.update(name+'::'+ident for ident,value in new.items() if old.get(ident)!=value)
    return changed

def pytest_failure_is_from_changed_test(node,changed_nodes):
    if '::' not in node:
        # Pytest may emit a second bare ERROR filename for an import failure
        # inside an already-identified test. Treat it as new only if that file
        # itself, rather than a nested test, is the revised acceptance target.
        return any(item.split('::',1)[0]==node for item in changed_nodes)
    path,case=node.split('::',1);case=case.split('[',1)[0]
    return any(item.startswith(path+'::') and case==item.split('::',1)[1] for item in changed_nodes)

def baseline_pytest_safe(repo,tests):
    # Avoid replaying suites that advertise live HTTP/service dependencies.
    markers=(b'httpbin(',b'requires_network',b'requires-internet',b'live_server',b'@pytest.mark.integration')
    for name in tests:
        try:body=(Path(repo)/name).read_bytes().lower()
        except OSError:return False
        if any(marker in body for marker in markers):return False
    return True

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
    if(run/'acceptance-history.json').exists():sealed(run,'acceptance-history.json')
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
    if (run/'acceptance-history.json').exists():
        history=sealed(run,'acceptance-history.json');result['acceptance_amendments']=len(history)
        result['preserved_failed_checks']=sum(sum(not row['passed'] for row in item['attempts'][-1].get('checks',[])) for item in history if item.get('attempts'))
        result['amendment_history']=[{'reason':item['reason'],'attempts':len(item['attempts']),'failed_checks':[{'suite':row['suite'],'id':row['id'],'returncode':row.get('returncode')}for row in item['attempts'][-1].get('checks',[])if not row['passed']]}for item in history]
    result['test_revisions']=len(s.get('test_revisions',[]))
    result['superseded_test_files']=sorted({p for revision in s.get('test_revisions',[]) for p in revision.get('superseded_tests',[])})
    latest=s['attempts'][-1]if s['attempts']else{}
    result['checks_passed']=sum(row['passed']for row in latest.get('checks',[]))
    result['checks_total']=len(latest.get('checks',[]))
    if latest:
        checks=sealed(run,'acceptance.json')['checks'];diagnostic_ids={row['id']for row in checks if row.get('diagnostic',False)}
        def log_name(row):return None if row.get('skipped')else f"attempt-{len(s['attempts'])}/{row['suite']}-{next(i for i,x in enumerate(checks)if x['id']==row['id'])}.log"
        result['diagnostic_checks']=[{'suite':row['suite'],'id':row['id'],'passed':row['passed'],'skipped':row.get('skipped',False),'returncode':row.get('returncode'),'seconds':row.get('seconds'),'log':log_name(row)}for row in latest.get('checks',[])if row['id']in diagnostic_ids]
        result['skipped_original_checks']=[{'id':row['id'],'reason':row.get('skip_reason')}for row in latest.get('checks',[])if row.get('skipped')]
    result['baseline_adjusted_checks']=[{'suite':row['suite'],'id':row['id'],'preexisting_failure_count':len(row.get('preexisting_failures',[])),'examples':row.get('preexisting_failures',[])[:5]}for row in latest.get('checks',[])if row.get('baseline')=='no_new_pytest_failures']
    result['criteria']=[{'id':'c'+str(n),'status':i['status'],**({'quote':i['quote'],'blocker':i.get('blocker','')}if i['status']!='verified'else{})}for n,i in enumerate(latest.get('criteria',[]),1)]
    result['evidence']=str(run)
    result['next_action']='stop'if s.get('goal_complete')and not stale else'implement'if not s['attempts']else'repair_source_or_justify_builder_draft_revision'
    if latest and not stale and all(row['passed']for row in latest.get('checks',[]))and any(i['status']=='blocked'for i in latest.get('criteria',[])):result['next_action']='stop_blocked'
    failures=[]
    diagnostic_ids={row['id']for row in sealed(run,'acceptance.json')['checks']if row.get('diagnostic',False)} if latest else set()
    for row in latest.get('checks',[]):
        if row['passed']or row['id']in diagnostic_ids:continue
        item={k:v for k,v in row.items()if k not in ('preexisting_failures',)};path=run/('attempt-'+str(len(s['attempts'])))/(row['suite']+'-'+str([c['id']for c in sealed(run,'acceptance.json')['checks']].index(row['id']))+'.log');item['log']=str(path)
        if path.exists():
            with path.open('rb')as stream:
                stream.seek(max(0,path.stat().st_size-1200))
                item['output_tail']=stream.read(1200).decode('utf-8',errors='replace')
        failures.append(item)
    result['failed_checks']=failures
    result.update(elapsed_seconds=round(elapsed(c),3),remaining_seconds=max(0,round(c['wall_seconds']-elapsed(c),3)),engine_model_calls=0,caller_usage='UNKNOWN',stale=stale,goal_complete=bool(s.get('goal_complete')and not stale))
    if stale and s['status']in('verified','incomplete'):result['status']='stale'
    return result

def check_covers_test_file(check,repo,name):
    if check.get('diagnostic',False):return False
    root=Path(repo).resolve();cwd=check.get('cwd','.');working=(root/cwd).resolve();argv=check['argv'];target=Path(name)
    skip={'-k','-m','-c','--confcutdir','--rootdir','-o','--override-ini','--deselect','--ignore','--ignore-glob'}
    ignored_next=False
    for arg in argv:
        if ignored_next:ignored_next=False;continue
        if arg in skip:ignored_next=True;continue
        module_name=target.with_suffix('').as_posix().replace('/','.')
        if arg in (target.stem,module_name):return True
        raw=arg.split('::',1)[0]
        if not raw or raw.startswith('-'):continue
        candidate=Path(raw)
        if not candidate.is_absolute():candidate=working/candidate
        try:candidate=candidate.resolve();candidate.relative_to(root)
        except (OSError,ValueError):continue
        if candidate.is_file()and candidate.relative_to(root).as_posix()==name:return True
        if candidate.is_dir():
            try:(candidate/target.relative_to(candidate.relative_to(root))).resolve()
            except ValueError:continue
            if (candidate/target.relative_to(candidate.relative_to(root))).is_file():return True
    # Recognized unfiltered full-suite commands cover every original test file.
    for index,arg in enumerate(argv):
        if Path(arg).name=='pytest':
            tail=argv[index+1:]
            if not any(x in skip or x.startswith(('-k','-m','--ignore','--deselect'))for x in tail)and not any((working/x.split('::',1)[0]).exists()for x in tail if not x.startswith('-')):return True
        if arg=='unittest'and'discover'in argv[index+1:]:return True
        if arg=='unittest'and not argv[index+1:]:return True
        if arg=='npm'and index+1<len(argv)and argv[index+1]=='test'and not any((working/x).exists()for x in argv[index+2:]if not x.startswith('-')):return True
        if arg in ('mvn','gradle','cargo')and any(x in ('test','check')for x in argv[index+1:]):return True
        if Path(arg).name in ('mvnw','gradlew')and any(x in ('test','check')for x in argv[index+1:]):return True
        if arg=='go'and'test'in argv[index+1:]and any(x in('./...','all')for x in argv[index+1:]):return True
    return False

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
        print('DELIVERY: Map requested outcomes—not anecdotes or historical context—into 1–8 criteria. Link each criterion to direct checks. Use diagnostic:true for broader or unavailable-environment checks that should run and be reported without gating a directly verified criterion. Example: '+json.dumps({'checks':[{'id':'focused','argv':['python3','check.py']},{'id':'integration','argv':['python3','integration.py'],'diagnostic':True}],'criteria':[{'quote':'EXACT REQUESTED OUTCOME','checks':['focused']}]}))
        print('Use the documented full project check runner plus focused behavior tests; never assume a bare compiler command exists or replace/skip original tests. In this SAME implementation command save criteria and run: '+sys.executable+' '+str(Path(__file__).resolve())+' deliver '+str(run)+' --criteria-file CRITERIA')
        print('Use checks:[] plus a blocker for an explicitly required but unverifiable outcome. Treat historical versions and hypotheses as context unless the requested change requires them. Keep accepted tests immutable; correct a draft only before its first green run and with a specification-based reason. On goal_complete:true stop immediately: no status/finish rerun. Preserve all requested outcomes; authored tests are not independent semantic proof.')
    return 0

def validate_acceptance(run,c,data):
    checks=data.get('checks',[]);criteria=data.get('criteria',[])
    if not isinstance(checks,list)or len(checks)>16 or not isinstance(criteria,list)or not 1<=len(criteria)<=8:raise ValueError('Expected 1–8 criteria and <=16 checks')
    paths=data.get('test_paths',[])
    if not isinstance(paths,list)or any(not isinstance(p,str)or not p or '\\'in p or Path(p).is_absolute()or '..'in Path(p).parts or p!=Path(p).as_posix()for p in paths):raise ValueError('test_paths must be relative files or directories')
    ids=[]
    for check in checks:
        ident=check.get('id');argv=check.get('argv')
        if not isinstance(ident,str)or not ident.strip()or ident in ids or not isinstance(argv,list)or not argv or any(not isinstance(v,str)or '\0'in v for v in argv)or not isinstance(check.get('diagnostic',False),bool):raise ValueError('Unique check IDs, argv lists, and boolean diagnostic flags required')
        cwd=check.get('cwd','.')
        if not isinstance(cwd,str)or not cwd or '\\'in cwd or Path(cwd).is_absolute()or '..'in Path(cwd).parts:raise ValueError('Check cwd must stay inside repository')
        if not(Path(c['repo'])/cwd).is_dir():raise ValueError('Check cwd must exist')
        ids.append(ident)
    for check in checks:validate_pytest_node_args(check,Path(c['repo']))
    goal=(run/'goal.bin').read_bytes().decode('utf-8')
    for item in criteria:
        quote=item.get('quote');links=item.get('checks');blocker=item.get('blocker','')
        if not isinstance(quote,str)or not quote.strip()or quote not in goal:raise ValueError('Criterion must quote the original goal')
        if not isinstance(links,list)or any(x not in ids for x in links)or len(set(links))!=len(links)or not isinstance(blocker,str)or not links and not blocker.strip():raise ValueError('Criterion needs valid checks or an explicit blocker')
    linked={x for i in criteria for x in i['checks']}
    required={check['id']for check in checks if not check.get('diagnostic',False)}
    if required!=linked or any(check.get('diagnostic',False)and check['id']in linked for check in checks):raise ValueError('Every required check must support a criterion; diagnostic checks stay unlinked')
    repo=Path(c['repo']);files=inventory(repo);tests=test_names(files,paths)
    original_test_files=test_names(c['original'],paths)
    changed_test_files={name for name in set(tests)|set(original_test_files)if tests.get(name)!=original_test_files.get(name)}
    for name in sorted(changed_test_files):
        if not any(check_covers_test_file(check,repo,name)for check in checks if not check.get('diagnostic',False)):
            raise ValueError('Changed test file needs a required check that runs it: '+name)
    if any(not any(n==p or n.startswith(p+'/')for n in set(files)|set(c['original']))for p in paths):raise ValueError('test_paths must match captured files')
    result={'checks':checks,'criteria':criteria,'tests':tests,'test_paths':paths}
    return result

def acceptance(run,c,data):
    result=validate_acceptance(run,c,data)
    copy_files(Path(c['repo']),run/'builder-tests',result['tests'])
    seal(run,'acceptance.json',result)
    return result

def amend_acceptance(run,c,s,data,reason):
    """Revise failed acceptance without discarding its exact prior evidence."""
    if not reason or len(reason)>2000:raise ValueError('A concise amendment reason is required')
    if s.get('goal_complete') or (run/'accepted-tests.json').exists():raise ValueError('Verified acceptance is immutable')
    if not s.get('attempts'):raise ValueError('Run the frozen acceptance once before amending it')
    old=sealed(run,'acceptance.json');latest=s['attempts'][-1];result=read(data)
    if result.get('test_paths',[])!=old.get('test_paths',[]):raise ValueError('Amendment cannot narrow or replace captured test paths')
    old_checks={x['id']:x for x in old['checks']};new_checks={x['id']:x for x in result.get('checks',[])}
    failed={x['id'] for x in latest['checks'] if not x['passed']}
    if not set(old_checks).issubset(new_checks):raise ValueError('Amendment cannot remove prior checks')
    for ident,check in old_checks.items():
        revised=dict(new_checks[ident]);prior=dict(check)
        if revised!=prior:
            allowed=dict(prior);allowed['diagnostic']=True
            if ident not in failed or prior.get('diagnostic',False) or revised!=allowed:raise ValueError('Only a failed required check may become diagnostic')
    old_criteria={x['quote']:x for x in old['criteria']};new_criteria={x['quote']:x for x in result.get('criteria',[])}
    if len(old_criteria)!=len(old['criteria']) or len(new_criteria)!=len(result.get('criteria',[])) or set(old_criteria)!=set(new_criteria):raise ValueError('Amendment must preserve every unique original criterion quote')
    for quote,item in old_criteria.items():
        revised=new_criteria[quote]
        if revised.get('blocker','')!=item.get('blocker',''):raise ValueError('Amendment cannot weaken or add blockers')
        if not (set(item['checks'])-failed).issubset(set(revised.get('checks',[]))):raise ValueError('Amendment must retain passing evidence links')
    validated=validate_acceptance(run,c,result)
    history=read(run/'acceptance-history.json') if (run/'acceptance-history.json').exists() else []
    history.append({'reason':reason,'acceptance':old,'attempts':s['attempts']})
    seal(run,'acceptance-history.json',history)
    copy_files(Path(c['repo']),run/'builder-tests',validated['tests'])
    seal(run,'acceptance.json',validated)
    return validated

def verify(run,c,s,revision=None,supersede_tests=None):
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
    if accepted and supersede_tests:raise ValueError('Accepted test semantics are frozen; start a new session to change them')
    if supersede_tests and current==active['files'] and not revision:raise ValueError('A test-revision rationale is required to supersede old expectations')
    if supersede_tests and current==active['files'] and revision:
        original_test_files=test_names(c['original'],ac.get('test_paths',[]),expanded='test_paths'in ac)
        superseded=validate_superseded(repo,run/'original',original_test_files,current,supersede_tests)
        for name in sorted(superseded):
            if not any(check_covers_test_file(check,repo,name)for check in ac['checks']if not check.get('diagnostic',False)):
                raise ValueError('Superseded test file needs a required check that runs it: '+name)
        folder='test-revisions/'+str(len(s.get('test_revisions',[]))+1)
        if(run/folder).exists():raise ValueError('Existing test revision preserved')
        copy_files(repo,run/folder,current)
        active={'files':current,'directory':folder,'reason':revision.strip(),'superseded_tests':sorted(superseded)}
        s.setdefault('test_revisions',[]).append(active);seal(run,'state.json',s)
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
        changed_test_files={name for name in set(active['files'])|set(current)if active['files'].get(name)!=current.get(name)and is_test(name)}
        for name in sorted(changed_test_files):
            if not any(check_covers_test_file(check,repo,name)for check in ac['checks']if not check.get('diagnostic',False)):
                raise ValueError('Revised test file needs a required check that runs it: '+name)
        folder='test-revisions/'+str(len(s.get('test_revisions',[]))+1)
        if(run/folder).exists():raise ValueError('Existing test revision preserved')
        original_test_files=test_names(c['original'],ac.get('test_paths',[]),expanded='test_paths'in ac)
        superseded=set(active.get('superseded_tests',[]))|validate_superseded(repo,run/'original',original_test_files,current,supersede_tests or [])
        for name in sorted(superseded):
            if not any(check_covers_test_file(check,repo,name)for check in ac['checks']if not check.get('diagnostic',False)):
                raise ValueError('Superseded test file needs a required check that runs it: '+name)
        copy_files(repo,run/folder,current)
        active={'files':current,'directory':folder,'reason':revision.strip(),'superseded_tests':sorted(superseded)}
        s.setdefault('test_revisions',[]).append(active);seal(run,'state.json',s)
    test_files=active['files'];test_folder=run/active['directory']
    rows=[];attempt=run/f'attempt-{len(s["attempts"])+1}';attempt.mkdir()
    original_tests=test_names(c['original'],ac.get('test_paths',[]),expanded='test_paths'in ac)
    superseded=set(active.get('superseded_tests',[]))
    original_tests={n:sha for n,sha in original_tests.items() if n not in superseded}
    # Builder includes byte-identical originals once. For append-only Python test
    # additions, its complete suite also runs every original byte unchanged, so a
    # second full original suite adds no coverage and can double verification cost.
    # Non-additive originals still run separately unless explicitly superseded.
    suites=[('builder',test_files,test_folder)]
    needs_original=any(test_files.get(n)!=sha and not test_file_is_additive(run/'original',test_folder,n) for n,sha in original_tests.items())
    if original_tests and needs_original:suites.insert(0,('original',original_tests,run/'original'))
    for label,tests,frozen in suites:
        with tempfile.TemporaryDirectory(prefix='goalpilot-native-')as tmp:
            work=Path(tmp);copy_files(repo,work,source)
            for name in source:
                if name in current and name not in tests:(work/name).unlink()
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
                missing_original_nodes=label=='original' and pytest_nodes_exist_in_snapshot(check,repo,run/'original',original_tests) is False
                if missing_original_nodes:row.update(passed=True,skipped=True,skip_reason='explicit pytest node is absent from the frozen original suite; the required builder check still runs')
                elif remaining<=0:row.update(blocked=True,error='deadline')
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
                argv=check['argv']
                full_pytest=any(Path(a).name=='pytest'for a in argv) and not is_focused_check(argv)
                if not row['passed'] and not row['blocked'] and full_pytest and baseline_pytest_safe(repo,tests):
                    baseline_log=attempt/(label+'-'+str(ac['checks'].index(check))+'-baseline.log')
                    candidate_ids=pytest_failure_ids(log)
                    baseline_files=pytest_failure_files(log,repo,check.get('cwd','.'))
                    baseline_argv=selective_pytest_command(argv,baseline_files)
                    if baseline_argv is None:baseline_argv=argv
                    baseline_scope='failing_test_files'if baseline_argv!=argv else'full_suite'
                    remaining=c['wall_seconds']-elapsed(c);base_code=None;base_ids=set();base_seconds=0.0
                    if remaining>0:
                        base_start=time.monotonic()
                        with tempfile.TemporaryDirectory(prefix='goalpilot-baseline-')as tmp:
                            base=Path(tmp);original_test_names=test_names(c['original'],ac.get('test_paths',[]),expanded='test_paths'in ac)
                            base_files={n:v for n,v in c['original'].items()if n not in original_test_names}
                            copy_files(run/'original',base,base_files)
                            for name in original_test_names:
                                p=base/name
                                if p.exists():p.unlink()
                            copy_files(frozen,base,tests)
                            for dep in ('node_modules','.venv','venv'):
                                p=repo/dep
                                if p.is_dir():
                                    try:(base/dep).symlink_to(p,target_is_directory=True)
                                    except OSError:pass
                            try:
                                with baseline_log.open('wb')as stream:
                                    proc=subprocess.Popen(baseline_argv,cwd=base/check.get('cwd','.'),stdout=stream,stderr=subprocess.STDOUT,start_new_session=os.name!='nt')
                                    try:base_code=proc.wait(timeout=remaining)
                                    except subprocess.TimeoutExpired:
                                        if os.name!='nt':
                                            import signal
                                            os.killpg(proc.pid,signal.SIGKILL)
                                        else:proc.kill()
                                        proc.wait()
                                base_ids=pytest_failure_ids(baseline_log)
                            except (OSError,subprocess.TimeoutExpired):base_code=None
                        base_seconds=time.monotonic()-base_start
                    candidate_ids=pytest_failure_ids(log)
                    changed_nodes=changed_pytest_nodes(run/'original',original_tests,test_folder,test_files)
                    has_new_case_failure=any(pytest_failure_is_from_changed_test(node,changed_nodes)for node in candidate_ids)
                    if base_code not in (None,0) and base_ids and candidate_ids and candidate_ids.issubset(base_ids)and not has_new_case_failure:
                        row.update(passed=True,baseline='no_new_pytest_failures',baseline_returncode=base_code,
                                   baseline_seconds=round(base_seconds,3),baseline_scope=baseline_scope,
                                   baseline_test_files=baseline_files if baseline_scope=='failing_test_files' else [],
                                   preexisting_failures=sorted(candidate_ids&base_ids))
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
    for name in ('deliver','amend','finish','status'):
        p=sub.add_parser(name);p.add_argument('run_dir',type=Path)
        if name in ('deliver','amend'):p.add_argument('--criteria-file',type=Path,required=True)
        if name=='amend':p.add_argument('--reason',required=True)
        if name=='finish':
            p.add_argument('--test-revision');p.add_argument('--supersede-tests',action='append',default=[])
    args=sys.argv[1:]
    if args and args[0]=='session':args=args[1:]
    a=parser.parse_args(args)
    try:
        if a.command=='begin':return begin(a)
        run=a.run_dir.absolute()
        if (run/'session-state.json').exists():
            if a.command=='amend':raise ValueError('Acceptance amendments require the native workflow')
            if getattr(a,'test_revision',None) or getattr(a,'supersede_tests',[]):raise ValueError('Test-draft revisions apply to native sessions only; the specialized engine keeps its original frozen acceptance')
            return legacy_command(run,a.command,getattr(a,'criteria_file',None))
        c,s=load(run)
        if a.command=='status':print(json.dumps(report(run,c,s),ensure_ascii=False));return 0
        if a.command=='deliver':
            if(run/'acceptance.json').exists():raise ValueError('Acceptance frozen: repair then finish')
            acceptance(run,c,read(a.criteria_file))
        if a.command=='amend':
            if not(run/'acceptance.json').exists():raise ValueError('Deliver acceptance before amending it')
            amend_acceptance(run,c,s,a.criteria_file,a.reason)
        return verify(run,c,s,getattr(a,'test_revision',None),getattr(a,'supersede_tests',[]))
    except (OSError,ValueError,KeyError,TypeError)as exc:
        print(json.dumps({'status':'blocked','goal_complete':False,'error':str(exc)}));return 2

if __name__=='__main__':raise SystemExit(main())
