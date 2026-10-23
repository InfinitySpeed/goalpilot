#!/usr/bin/env python3
"""Launch Codex with one reviewed GoalPilot hook set; preserve unrelated hooks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys

BUNDLE=Path(__file__).resolve().parents[1]


def engine_identity(bundle):
    bundle=Path(bundle).resolve()
    manifest=json.loads((bundle/'MANIFEST.json').read_text())
    if manifest.get('package')!='goalpilot-codex-skill':raise ValueError('Not a GoalPilot bundle')
    actual={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in (bundle/'runtime/goalpilot').glob('*.py')}
    if not actual or actual!=manifest['engine']['files']:raise ValueError('Embedded engine differs from its manifest')
    launcher=bundle/'scripts/goalpilot.py'
    digest=hashlib.sha256(launcher.read_bytes()).hexdigest()
    if manifest['files'].get('scripts/goalpilot.py')!=digest:raise ValueError('Launcher differs from its manifest')
    return {'engine_files':actual,'launcher_sha256':digest}


def known_identities():
    return [engine_identity(BUNDLE),json.loads((BUNDLE/'references/legacy-hook-identity.json').read_text())]


def duplicate_keys(reply,owned,identities):
    keys=[];own_keys={h['key']for h in owned}
    for row in reply['data']:
        for h in row.get('hooks',[]):
            if h['key']in own_keys or not h.get('enabled')or h.get('trustStatus')!='trusted':continue
            if h.get('handlerType')!='command'or h.get('async',False):continue
            event=h.get('eventName')
            if event not in ('preToolUse','postToolUse','stop'):continue
            if h.get('timeoutSec')!=(180 if event=='stop'else 120):continue
            if event!='stop'and h.get('matcher')!='^(Bash|apply_patch)$':continue
            try:
                parts=shlex.split(h['command'])
                if len(parts)!=3 or parts[2]!='hook':continue
                path=Path(parts[1])
                if path.name!='goalpilot.py'or path.parent.name!='scripts'or path.is_symlink():continue
                ident=engine_identity(path.parents[1])
                if ident not in identities:continue
            except (OSError,ValueError,KeyError,TypeError):continue
            if h.get('isManaged'):raise ValueError('Managed duplicate GoalPilot hook requires its normal configuration workflow')
            keys.append(h['key'])
    return keys


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,default=BUNDLE)
    p.add_argument('--codex-executable',default='codex')
    p.add_argument('--audit-only',action='store_true',help='Review configuration only; zero model calls.')
    p.add_argument('--receipt',type=Path)
    p.add_argument('codex_args',nargs=argparse.REMAINDER)
    a=p.parse_args(argv)
    try:
        if os.name=='nt':raise ValueError('Use explicit portable verification on Windows')
        identities=known_identities();target=engine_identity(a.bundle)
        if target not in identities:raise ValueError('Target is not an exact recognized GoalPilot engine/launcher')
        sys.path.insert(0,str(a.bundle.resolve()/'runtime'))
        from goalpilot.hook_config import ConfigRPC,definitions,review,toml
        launcher=a.bundle.resolve()/'scripts/goalpilot.py'
        defs=definitions(launcher);override='hooks='+toml(defs)
        with ConfigRPC(a.codex_executable,[override])as rpc:
            reply=rpc.request('hooks/list',{'cwds':[str(Path.cwd())]})
        owned,state=review(reply,defs,source='sessionFlags')
        duplicate=duplicate_keys(reply,owned,identities)
        for key in duplicate:state[key]={**state.get(key,{}),'enabled':False}
        state_override='hooks.state='+toml(state)
        with ConfigRPC(a.codex_executable,[override,state_override])as rpc:
            effective=rpc.request('hooks/list',{'cwds':[str(Path.cwd())]})
        effective_hooks={h['key']:h for row in effective['data']for h in row.get('hooks',[])}
        if any(effective_hooks.get(k,{}).get('enabled')is not False for k in duplicate):
            raise ValueError('Duplicate hook disablement was not applied')
        if any(not effective_hooks.get(h['key'],{}).get('enabled')or effective_hooks[h['key']].get('trustStatus')!='trusted'for h in owned):
            raise ValueError('Reviewed GoalPilot hooks are not active and trusted')
        receipt={'effective_configuration_verified':True,'model_calls':0,'owned_hook_keys':[h['key']for h in owned],
                 'disabled_exact_duplicate_keys':duplicate,'global_settings_changed':False,
                 'unrelated_hooks_preserved':True,'scope':'Exact reviewed process-only hooks.state; no permission/approval bypass.'}
        if a.receipt:
            a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
        if a.audit_only:print(json.dumps(receipt,indent=2));return 0
        args=a.codex_args[1:]if a.codex_args[:1]==['--']else a.codex_args
        if not args:p.error('Supply Codex arguments after --, or use --audit-only')
        os.execvp(a.codex_executable,[a.codex_executable,*args,'-c',override,'-c',state_override])
    except (OSError,ValueError,KeyError,TypeError)as exc:
        print('GoalPilot Codex setup: '+str(exc),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
