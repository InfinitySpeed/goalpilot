"""Exact-input verified patch reuse. New/changed requests always execute normally."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import sys
import tempfile
import time
from . import __version__
from .engine import atomic_json, artifacts_intact, lock, token_totals, verify
from .model import ContractError, digest, validate

SKIP={'__pycache__','.pytest_cache','.mypy_cache'}
PATCHABLE={'.py','.js','.ts','.jsx','.tsx','.go','.rs','.java','.css','.html','.sql','.sh','.md','.toml','.txt','.json','.yml','.yaml'}


def inventory(repo, *, exclude=()):
    """Bounded, complete regular-file inventory; omitted inputs disable reuse."""
    root=Path(repo).resolve();files={};total=0
    for directory,dirs,names in os.walk(root,followlinks=False):
        dirs[:]=sorted(d for d in dirs if d not in SKIP and d not in exclude)
        for d in dirs:
            if (Path(directory)/d).is_symlink():raise ValueError('Symlink directory disables reuse')
        for name in sorted(names):
            p=Path(directory)/name;rel=p.relative_to(root).as_posix()
            if p.is_symlink()or not p.is_file():raise ValueError('Non-regular file disables reuse')
            lower=name.lower()
            if name.startswith('.env')or any(w in lower for w in ('credential','secret','auth.json','id_rsa','id_ed25519'))or p.suffix in ('.key','.pem'):
                raise ValueError('Sensitive file disables reuse')
            size=p.stat().st_size;total+=size
            if size>4000000 or total>16000000 or len(files)>=2000:raise ValueError('Inventory bounds disable reuse')
            files[rel]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mode':stat.S_IMODE(p.stat().st_mode)}
    ancestors={}
    for parent in root.parents:
        p=parent/'AGENTS.md'
        if p.is_symlink():raise ValueError('Symlink instruction disables reuse')
        if p.is_file():ancestors[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    return {'files':files,'ancestor_instructions':ancestors,'runtime':[sys.version,platform.platform()]}


def _translate(value,old,new):
    if isinstance(value,dict):return {k:_translate(v,old,new)for k,v in value.items()}
    if isinstance(value,list):return [_translate(v,old,new)for v in value]
    if isinstance(value,str)and old in value:
        if value==old or value.startswith(old+'/'):return new+value[len(old):]
        raise ValueError('Embedded absolute project path is not safely relocatable')
    return value


def publish(cache, goal, model, before, repo, run_dir, state):
    if state['status']not in ('scope_passed','completed')or not state.get('calls')or not state['usage']['usage_complete']:return False
    if state['contract'].get('acceptance_origin')!='builder_frozen':return False
    after=inventory(repo);old=before['files'];new=after['files']
    if not old.keys()<=new.keys():return False # No deletion replay.
    changed=[p for p in new if new[p]!=old.get(p)]
    if not changed or any(Path(p).suffix not in PATCHABLE or '.git' in Path(p).parts for p in changed):return False
    if any(p in old and Path(p).suffix in ('.json','.txt','.yml','.yaml') and
           Path(p).name not in ('package.json','requirements.txt') for p in changed):return False
    # Existing mutable JSON/text data cannot be rewritten by a replay.
    if not artifacts_intact(state['contract']):return False
    key=digest([__version__,goal,model,before]);cache=Path(cache);cache.mkdir(parents=True,exist_ok=True,mode=0o700)
    with lock(cache/'publish.lock'):
        target=cache/key
        if target.exists():return False
        with tempfile.TemporaryDirectory(dir=cache,prefix='publish-')as tmp:
            tmp=Path(tmp);payload=tmp/'patch';payload.mkdir()
            for rel in changed:
                dst=payload/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(Path(repo)/rel,dst)
            entry={'key':key,'version':__version__,'goal':goal,'model':model,'before':before,'after':after,
                   'changed':changed,'source_repo':str(Path(repo).resolve()),'source_run':str(Path(run_dir).resolve()),
                   'contract':state['contract'],'training_usage':state['usage'],'training_seconds':state['active_seconds'],
                   'simulated':state.get('simulated',False)}
            atomic_json(tmp/'entry.json',entry)
            atomic_json(tmp/'receipt.json',{'entry_sha256':hashlib.sha256((tmp/'entry.json').read_bytes()).hexdigest()})
            os.rename(tmp,target)
        final_key=digest([__version__,goal,model,after])
        atomic_json(cache/(final_key+'.json'),{'primary_key':key})
    return True


def replay(cache, goal, model, before, repo, run_dir, wall_seconds):
    start=time.monotonic();deadline=start+wall_seconds;repo=Path(repo).resolve();run_dir=Path(run_dir).resolve()
    if run_dir==repo or repo in run_dir.parents:raise ContractError('Evidence must live outside repository')
    if (run_dir/'state.json').exists()or(run_dir/'finish-run.json').exists():raise ContractError('Run exists; continue its existing mission')
    key=digest([__version__,goal,model,before]);entry_dir=Path(cache)/key
    try:
        if not entry_dir.is_dir():
            alias=Path(cache)/(key+'.json')
            if not alias.is_file():return None
            primary=json.loads(alias.read_text()).get('primary_key')
            if not isinstance(primary,str)or len(primary)!=64 or any(c not in '0123456789abcdef'for c in primary):raise ValueError('Invalid alias')
            entry_dir=Path(cache)/primary
        raw=(entry_dir/'entry.json').read_bytes();receipt=json.loads((entry_dir/'receipt.json').read_text())
        if hashlib.sha256(raw).hexdigest()!=receipt['entry_sha256']:raise ValueError('Entry integrity mismatch')
        entry=json.loads(raw)
        if entry['key']!=digest([__version__,goal,model,entry['before']]) or entry['goal']!=goal or entry['model']!=model:raise ValueError('Exact input mismatch')
        after=entry['after'];changed=entry['changed'];already_delivered=before==after
        if before!=entry['before']and not already_delivered:raise ValueError('Exact input mismatch')
        expected=[p for p in after['files']if after['files'][p]!=entry['before']['files'].get(p)]
        if sorted(changed)!=sorted(expected)or not entry['before']['files'].keys()<=after['files'].keys():raise ValueError('Invalid patch inventory')
        apply_changes=[]if already_delivered else changed
        for rel in changed:
            p=Path(rel)
            if p.is_absolute()or '..'in p.parts or p.suffix not in PATCHABLE or '.git'in p.parts:raise ValueError('Invalid patch path')
            src=entry_dir/'patch'/p
            if src.is_symlink()or hashlib.sha256(src.read_bytes()).hexdigest()!=after['files'][rel]['sha256']:raise ValueError('Patch integrity mismatch')
        with tempfile.TemporaryDirectory(prefix='goalpilot-reuse-',dir=repo.parent)as tmp:
            stage=Path(tmp)/'repo';shutil.copytree(repo,stage,ignore=shutil.ignore_patterns(*SKIP))
            for rel in apply_changes:
                dst=stage/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(entry_dir/'patch'/rel,dst)
                dst.chmod(after['files'][rel]['mode'])
            if inventory(stage)!=after:raise ValueError('Staged result does not match the verified delivery')
            contract=_translate(entry['contract'],entry['source_repo'],str(stage))
            checks=verify(contract,deadline,run_dir/'evidence/reuse')
            if not checks or not all(c['passed']for c in checks):raise ValueError('Cached acceptance failed; normal execution required')
            # The cached tests run against disposable data. Refuse test-induced source/data edits.
            if inventory(stage)!=after:raise ValueError('Verification mutated staged files')
            if inventory(repo)!=before:raise ValueError('Repository changed during verification')
            # A failed copy restores only the files touched by this replay.
            applied=[]
            try:
                for rel in apply_changes:
                    src=stage/rel;dst=repo/rel;backup=dst.read_bytes()if dst.exists()else None
                    applied.append((dst,backup,before['files'].get(rel,{}).get('mode')))
                    dst.parent.mkdir(parents=True,exist_ok=True)
                    with tempfile.NamedTemporaryFile(dir=dst.parent,delete=False)as stream:
                        temp=Path(stream.name);stream.write(src.read_bytes())
                    temp.chmod(after['files'][rel]['mode']);os.replace(temp,dst)
                if inventory(repo)!=after:raise ValueError('Committed replay inventory mismatch')
            except BaseException:
                for dst,backup,mode in reversed(applied):
                    if backup is None:dst.unlink(missing_ok=True)
                    else:dst.write_bytes(backup);dst.chmod(mode)
                raise
            contract=_translate(entry['contract'],entry['source_repo'],str(repo))
            state={'version':1,'id':key[:12],'contract':contract,'contract_hash':digest(contract),'mode':'supervised',
                   'status':'scope_passed','created_at':time.time(),'active_seconds':time.monotonic()-start,'calls':[],
                   'verifications':[{'checks':checks,'strategy':'exact-input-reuse','at':time.time(),'location':'disposable exact copy'}],
                   'pending':None,'no_progress':0,'best_passed':len(checks),'inactive_calls':0,'simulated':entry.get('simulated',False),
                   'adapter':{'class':'NoModelVerifiedReuse','model':model},'usage':token_totals([]),
                   'reuse':{'hit':True,'kind':'already_delivered'if already_delivered else 'initial_snapshot_replay','key':key,'source_run':entry['source_run'],'training_usage':entry['training_usage'],
                            'training_seconds':entry['training_seconds'],'model_calls':0,
                            'limitations':'Strictly identical goal and initial files only. Original learned acceptance rerun; no new independent completeness proof. Learning cost is not free.'}}
            atomic_json(run_dir/'mission.json',contract);atomic_json(run_dir/'state.json',state)
            return state
    except (OSError,ValueError,KeyError,TypeError)as exc:
        atomic_json(run_dir/'reuse-miss.json',{'reason':str(exc),'key':key,'model_calls':0})
        return None


def run_cached_finish(goal,repo,run_dir,*,cache,**options):
    """Try exact reuse; a miss delegates to the unchanged normal finish pipeline."""
    from .finish import run_finish
    start=time.monotonic();run_dir=Path(run_dir).resolve();repo=Path(repo).resolve();wall=options.get('wall_seconds',900)
    cache=Path(cache).resolve()
    if cache==repo or repo in cache.parents:raise ContractError('Cache must live outside repository')
    requested_budget={'wall_seconds':wall,'attempt_seconds':wall,'max_calls':options.get('max_calls',5),
                      'max_tokens':options.get('max_tokens',1000000)}
    if options.get('max_uncached_tokens')is not None:requested_budget['max_uncached_tokens']=options['max_uncached_tokens']
    validate({'goal':goal,'repo':str(repo),'budget':requested_budget,
              'checks':[{'id':'placeholder','description':'Budget validation only','command':['true']}]})
    with lock(run_dir/'reuse.lock'):
        if (options.get('audit_policy')!='on-interruption' or options.get('review_context')!='local' or options.get('resume')):
            state=run_finish(goal,repo,run_dir,**options)
            state['reuse']={'hit':False,'reason':'Requested review/resume policy requires its original pipeline','model_calls':len(state['calls'])}
            atomic_json(run_dir/'state.json',state)
            return state
        try:before=inventory(repo)
        except (OSError,ValueError):before=None
        if before is not None:
            state=replay(cache,goal,options.get('model'),before,repo,run_dir,wall)
            if state is not None:
                state['contract']['budget']=requested_budget
                state['contract_hash']=digest(state['contract'])
                atomic_json(run_dir/'mission.json',state['contract'])
                atomic_json(run_dir/'state.json',state)
                if options.get('notify'):options['notify']('Livraison réutilisée après revalidation locale : aucun appel modèle')
                return state
        else:
            atomic_json(run_dir/'reuse-miss.json',{'reason':'Complete eligible inventory unavailable','model_calls':0})
        remaining=wall-(time.monotonic()-start)
        if remaining<=0:raise ContractError('Deadline exhausted during local cache lookup')
        options={**options,'wall_seconds':remaining}
        state=run_finish(goal,repo,run_dir,**options)
        state['reuse']={'hit':False,'model_calls':len(state['calls']),'published':False}
        if before is not None:
            try:state['reuse']['published']=publish(cache,goal,options.get('model'),before,repo,run_dir,state)
            except (OSError,ValueError,KeyError):pass # Optional cache never changes delivery status.
        state['active_seconds']=time.monotonic()-start
        atomic_json(run_dir/'state.json',state)
        return state
