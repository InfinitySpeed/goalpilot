"""Install or launch reviewed local Codex hooks. Configuration RPC only, no inference."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import shlex
import signal
import subprocess
import sys
import threading
import time

from .engine import atomic_json
from .model import ContractError


def toml(value):
    if isinstance(value,str):return json.dumps(value,ensure_ascii=False)
    if isinstance(value,bool):return 'true'if value else'false'
    if type(value)is int:return str(value)
    if isinstance(value,list):return '['+','.join(toml(x)for x in value)+']'
    if isinstance(value,dict):return '{'+','.join(toml(k)+'='+toml(v)for k,v in value.items())+'}'
    raise ContractError('Unsupported configuration value')


def definitions(launcher):
    launcher=Path(launcher).resolve()
    if not launcher.is_file():raise ContractError('Missing portable GoalPilot launcher')
    command=shlex.join([sys.executable,str(launcher),'hook'])
    return {name:[{'matcher':'^(Bash|apply_patch)$','hooks':[{'type':'command','command':command,
                  'timeout':120,'additionalContextLimit':1500,'statusMessage':'GoalPilot local monitor'}]}]
            if name!='Stop'else[{'hooks':[{'type':'command','command':command,'timeout':180,'statusMessage':'GoalPilot local acceptance'}]}]
            for name in ('PreToolUse','PostToolUse','Stop')}


class ConfigRPC:
    """No thread/start, turn/start, goal/set, account or arbitrary tool method allowed."""
    METHODS={'initialize','hooks/list','config/batchWrite'}
    def __init__(self,executable,overrides=()):
        self.executable=executable;self.overrides=overrides;self.counter=0;self.inbox=queue.Queue()
    def __enter__(self):
        cmd=[self.executable,'app-server','--stdio']
        for override in self.overrides:cmd+=['-c',override]
        self.process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,start_new_session=True)
        def pump():
            try:
                for line in self.process.stdout:
                    try:self.inbox.put(json.loads(line))
                    except ValueError:pass
            finally:self.inbox.put(None)
        self.reader=threading.Thread(target=pump,daemon=True);self.reader.start()
        try:
            self.request('initialize',{'clientInfo':{'name':'goalpilot-reviewed-local-hooks','version':'0.11.0'},'capabilities':{'experimentalApi':True}})
            self.process.stdin.write('{"method":"initialized"}\n');self.process.stdin.flush()
        except BaseException:
            self.__exit__(None,None,None);raise
        return self
    def request(self,method,params,timeout=10):
        if method not in self.METHODS:raise ContractError('Hook configuration cannot launch inference or arbitrary RPC')
        self.counter+=1;ident=self.counter;until=time.monotonic()+timeout
        self.process.stdin.write(json.dumps({'id':ident,'method':method,'params':params})+'\n');self.process.stdin.flush()
        while True:
            try:reply=self.inbox.get(timeout=max(0,until-time.monotonic()))
            except queue.Empty:raise TimeoutError('Hook configuration RPC timeout')from None
            if reply is None:raise ContractError('Hook configuration server exited')
            if reply.get('id')==ident:
                if 'error'in reply:raise ContractError(str(reply['error']))
                return reply['result']
            if 'id'in reply and 'method'in reply:
                self.process.stdin.write(json.dumps({'id':reply['id'],'error':{'code':-32601,'message':'Configuration-only client; no approval/tool interaction'}})+'\n');self.process.stdin.flush()
    def __exit__(self,*_):
        try:
            self.process.stdin.close();self.process.wait(timeout=2)
        except (OSError,subprocess.TimeoutExpired):
            try:os.killpg(self.process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            self.process.wait(timeout=2)
        self.reader.join(timeout=1);self.process.stdout.close()


def review(reply,defs,*,source):
    expected={h['command']:True for groups in defs.values()for g in groups for h in g['hooks']}
    hooks=[h for row in reply['data']for h in row.get('hooks',[])]
    own=[h for h in hooks if h.get('command')in expected and h.get('source')==source]
    if len(own)!=3:raise ContractError('Expected exactly three authored hook definitions; refusing broad trust changes')
    if {h['eventName']for h in own}!={'preToolUse','postToolUse','stop'}:
        raise ContractError('Expected one monitor pair and one Stop hook')
    for h in own:
        if h.get('handlerType')!='command'or not h.get('enabled')or h.get('async',False):raise ContractError('Hook definition differs from synchronous local command')
        event=h['eventName'];want_timeout=180 if event=='stop' else 120
        if event not in ('preToolUse','postToolUse','stop')or h['timeoutSec']!=want_timeout:raise ContractError('Unexpected hook event or timeout')
        if event!='stop'and h.get('matcher')!='^(Bash|apply_patch)$':raise ContractError('Unexpected hook matcher')
    # Keep already trusted/disabled non-owned hooks effective; never trust new foreign hooks.
    state={}
    for h in hooks:
        if h.get('isManaged'):continue
        if h in own or h.get('trustStatus')=='trusted':state[h['key']]={'trusted_hash':h['currentHash'],'enabled':h['enabled']}
        elif h.get('enabled')is False:state[h['key']]={'enabled':False}
    return own,state


def launch(launcher,args,*,executable='codex'):
    defs=definitions(launcher);override='hooks='+toml(defs)
    with ConfigRPC(executable,[override])as client:
        reply=client.request('hooks/list',{'cwds':[str(Path.cwd())]})
    own,state=review(reply,defs,source='sessionFlags')
    receipt=os.environ.get('GOALPILOT_SETUP_RECEIPT')
    if receipt:atomic_json(Path(receipt),{'at':time.time(),'model_calls':0,'hook_keys':[h['key']for h in own],
                                      'trust':'exact reviewed process-only hashes; no bypass flag/global mutation'})
    os.execvp(executable,[executable,*args,'-c',override,'-c','hooks.state='+toml(state)])


def install(launcher,*,executable='codex',codex_dir=None):
    folder=Path(codex_dir)if codex_dir else Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
    if any(p.is_symlink()for p in (folder,*folder.parents)):raise ContractError('Codex config path must not be symlinked')
    folder.mkdir(parents=True,exist_ok=True)
    dest=folder/'hooks.json';defs=definitions(launcher)
    if dest.is_symlink():raise ContractError('Symlink hooks.json')
    before=dest.read_bytes()if dest.exists()else None
    old=json.loads(before)if before else{}
    if not isinstance(old,dict)or not isinstance(old.get('hooks',{}),dict):raise ContractError('Unexpected existing hook configuration')
    merged={**old,'hooks':{**old.get('hooks',{})}}
    commands={h['command']for groups in defs.values()for g in groups for h in g['hooks']}
    for name,groups in defs.items():
        existing=merged['hooks'].get(name,[])
        if not isinstance(existing,list):raise ContractError('Existing hooks must be arrays')
        # Never remove or rewrite another handler, including similarly named plugins.
        retained=[g for g in existing if not(g.get('hooks')and all(h.get('command')in commands for h in g['hooks']))]
        merged['hooks'][name]=retained+groups
    backup=folder/'goalpilot-hooks-backup.json'
    if before is not None and not backup.exists():
        atomic_json(backup,{'created_at':time.time(),'original_hooks_json':before.decode('utf-8')})
        backup.chmod(0o600)
    atomic_json(dest,merged)
    with ConfigRPC(executable)as client:
        reply=client.request('hooks/list',{'cwds':[str(Path.cwd())]})
        own,_=review(reply,defs,source='user')
        edits=[{'keyPath':'hooks.state.'+json.dumps(h['key'])+'.trusted_hash','value':h['currentHash'],'mergeStrategy':'upsert'}for h in own]
        client.request('config/batchWrite',{'edits':edits,'filePath':str(folder/'config.toml'),'reloadUserConfig':False})
    # Reopen to verify the persisted trust, rather than claiming activation from a write.
    with ConfigRPC(executable)as client:
        reply=client.request('hooks/list',{'cwds':[str(Path.cwd())]})
        own,_=review(reply,defs,source='user')
    if not all(h.get('trustStatus')=='trusted'for h in own):raise ContractError('Hooks installed but trust not active; inspect exact definitions')
    return {'status':'installed','hooks':3,'model_calls':0,'config':str(dest),'backup':str(backup)if before is not None else None,
            'hook_keys':[h['key']for h in own],'trust':'exact reviewed definitions only, no bypass'}


def main(argv=None,*,launcher=None):
    parser=argparse.ArgumentParser(description='GoalPilot local Codex hook configuration; zero inference')
    parser.add_argument('action',choices=['preview','install','launch'])
    parser.add_argument('--codex-executable',default='codex')
    parser.add_argument('arguments',nargs=argparse.REMAINDER)
    args=parser.parse_args(argv)
    if launcher is None:
        launcher=Path(sys.argv[0]).resolve()
        if launcher.name=='__main__.py':
            launcher=Path(__file__).resolve().parents[1]/'skills/goalpilot/scripts/goalpilot.py'
    try:
        if args.action=='preview':result={'hooks':definitions(launcher),'model_calls':0}
        elif args.action=='install':result=install(launcher,executable=args.codex_executable)
        else:
            rest=args.arguments[1:]if args.arguments[:1]==['--']else args.arguments
            launch(launcher,rest,executable=args.codex_executable);return 0
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except(OSError,ValueError,KeyError,TypeError,TimeoutError)as exc:
        print(json.dumps({'status':'unavailable','model_calls':0,'error':str(exc)},ensure_ascii=False),file=sys.stderr);return 2
