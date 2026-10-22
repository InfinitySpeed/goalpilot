#!/usr/bin/env python3
"""Agent-friendly local installation. Never starts models or edits host settings."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'skills/goalpilot'
HOSTS = ('codex', 'claude-code', 'antigravity', 'hermes', 'generic')
DESCRIPTION = 'A skill for coding agents that helps complete ambitious goals with local verification, focused repairs, and less repeated work.'


def base_installer():
    spec = importlib.util.spec_from_file_location('gp_bundle_installer', SOURCE/'scripts/install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hermes_home():
    if os.environ.get('HERMES_HOME'):
        return Path(os.environ['HERMES_HOME']).expanduser()
    if os.name == 'nt' and os.environ.get('LOCALAPPDATA'):
        return Path(os.environ['LOCALAPPDATA'])/'hermes'
    return Path.home()/'.hermes'


def detect_host():
    explicit = os.environ.get('GOALPILOT_HOST')
    if explicit in HOSTS:return explicit, 'GOALPILOT_HOST', []
    active = []
    if os.environ.get('CODEX_THREAD_ID'):active.append('codex')
    if os.environ.get('CLAUDECODE') or os.environ.get('CLAUDE_CODE_ENTRYPOINT'):active.append('claude-code')
    if len(active) == 1:return active[0], 'active-session environment', active
    known = []
    for host,path,executable in [('codex',Path.home()/'.codex','codex'),('claude-code',Path.home()/'.claude','claude'),('antigravity',Path.home()/'.gemini/config','agy'),('hermes',hermes_home(),'hermes')]:
        if path.exists() or shutil.which(executable):known.append(host)
    if len(known)==1:return known[0], 'single discovered host', known
    return 'generic', 'ambiguous or unknown host; portable entry only', known


def destinations(host,target=None):
    if target is not None:
        if host=='all':raise ValueError('--target requires a single host')
        return [(host,target.expanduser().absolute())]
    hosts=HOSTS[:-1] if host=='all' else (host,)
    folders={'codex':[Path.home()/'.agents/skills'],'claude-code':[Path.home()/'.claude/skills'],
        'antigravity':[Path.home()/'.gemini/config/skills',Path.home()/'.gemini/antigravity-cli/skills'],
        'hermes':[hermes_home()/'skills'],'generic':[(Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'GoalPilot/skills') if os.name=='nt' else Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'goalpilot/skills']}
    return [(name,folder/'goalpilot')for name in hosts for folder in folders[name]]


def preflight(target):
    if target.resolve()==SOURCE.resolve():raise ValueError('Cannot replace the source bundle')
    if target.is_symlink():raise ValueError('Refusing a symlink destination: '+str(target))
    if target.exists():
        previous=json.loads((target/'MANIFEST.json').read_text(encoding='utf-8'))
        if not isinstance(previous,dict)or previous.get('package')!='goalpilot-codex-skill':
            raise ValueError('Destination belongs to another skill: '+str(target))


def prepare_bundle(destination,host):
    shutil.copytree(SOURCE,destination,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    portable=host!='codex' or os.name=='nt'
    if portable:
        shutil.copy2(ROOT/'integrations/portable/SKILL.md',destination/'SKILL.md')
        shutil.copy2(ROOT/'integrations/portable/host.py',destination/'scripts/host.py')
    entry='scripts/host.py' if portable else 'scripts/goalpilot.py'
    skill=destination/'SKILL.md';body=skill.read_text(encoding='utf-8')
    note=('\n## Installed runtime\n\nUse the Python interpreter at `'+sys.executable+'` for EVERY command shown with python3. Do not rely on a system python3. Quote paths containing spaces; in PowerShell prefix a quoted executable with &. RUNTIME.json records the interpreter and entry point. No manual Python setup is needed.\n')
    skill.write_text(body.replace('# GoalPilot\n','# GoalPilot\n'+note,1),encoding='utf-8')
runtime={'python':sys.executable,'python_version':sys.version.split()[0],'entry_point':entry,'host':host,'engine_version':'0.15.0','adapter_version':'1.1.0'}
    (destination/'RUNTIME.json').write_text(json.dumps(runtime,indent=2)+'\n',encoding='utf-8')
    manifest=json.loads((destination/'MANIFEST.json').read_text(encoding='utf-8'))
    manifest.update(host_profile=host,adapter_version='1.1.0',entry_point=entry,
        completion_mode='explicit-session-finish'if portable else'codex-hooks-or-explicit-finish',
        measured_runtime_and_skill_parity=False,post_measurement_metadata_only=[],
        meter_scope='Historical benchmark: Codex skill1.3.1/engine0.12.1 only. Current engine, installer and adapters have not been model-benchmarked. Local verification launches no models.')
    for filename in ['measurements.json','baseline.json']:
        path=destination/'references'/filename
        if path.exists():
            value=json.loads(path.read_text(encoding='utf-8'))
            value.update(applies_to_current_bundle=False,current_measurement_applies=False,host_profile=host,host_adapter_benchmarked=False,reference_host='codex')
            if isinstance(value.get('accepted_future_targets'),dict):value['accepted_future_targets']['achieved']=False
            path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest['files']={p.relative_to(destination).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in sorted(destination.rglob('*'))if p.is_file()and'__pycache__'not in p.parts and p.suffix!='.pyc'and p!=destination/'MANIFEST.json'}
    (destination/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return destination


def doctor(installer,plan):
    rows=[]
    for host,target in plan:
        row={'host':host,'path':str(target),'ready':False}
        try:
            installer.validate(target)
            runtime=json.loads((target/'RUNTIME.json').read_text(encoding='utf-8'))
            p=subprocess.run([runtime['python'],'-X','utf8',str(target/runtime['entry_point']),'session','--help'],capture_output=True,text=True,timeout=20)
            row.update(ready=p.returncode==0,engine_version=runtime['engine_version'],error=None if p.returncode==0 else p.stderr[-1000:])
        except(OSError,ValueError,KeyError,subprocess.TimeoutExpired)as exc:row['error']=str(exc)
        rows.append(row)
    return {'ready':all(r['ready']for r in rows),'checks':rows,'model_calls':0}


def main():
    parser=argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('--host',choices=(*HOSTS,'auto','all','t3-code'),default='auto')
    parser.add_argument('--provider',choices=HOSTS,help='Underlying agent for --host t3-code.')
    parser.add_argument('--target',type=Path,help='Complete native skill directory for one host.')
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--doctor',action='store_true',help='Check installation/runtime without model calls.')
    args=parser.parse_args()
    try:
        if sys.version_info<(3,11):raise ValueError('Use bootstrap.sh or bootstrap.ps1 to prepare Python automatically')
        host=args.host;reason='explicit selection';candidates=[]
        if host=='t3-code':
            if not args.provider:raise ValueError('T3 Code uses an underlying agent: supply --provider codex, claude-code, antigravity, hermes or generic')
            host=args.provider;reason='T3 Code underlying provider'
        if host=='auto':host,reason,candidates=detect_host()
        plan=destinations(host,args.target);installer=base_installer()
        if args.doctor:
            result=doctor(installer,plan);print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['ready']else 1
        installer.validate(SOURCE)
        for _,target in plan:preflight(target)
        if args.dry_run:
            result={'selected_host':host,'selection_reason':reason,'candidates':candidates,'dry_run':True,'destinations':[{'host':name,'path':str(target)}for name,target in plan],'model_calls':0}
        else:
            rows=[]
            with tempfile.TemporaryDirectory(prefix='goalpilot-install-')as tmp:
                bundles={}
                for name,target in plan:
                    if name not in bundles:bundles[name]=prepare_bundle(Path(tmp)/name,name)
                    rows.append({'host':name,**installer.install(bundles[name],target),'skill_file':str(target/'SKILL.md')})
            verification=doctor(installer,plan)
            result={'selected_host':host,'selection_reason':reason,'installed':rows,'verification':verification,'model_calls':0,'host_settings_changed':False,'next_step':'Reload skills, then ask your agent to use GoalPilot. Generic hosts may need to read the returned skill_file explicitly.'}
            if not verification['ready']:print(json.dumps(result,ensure_ascii=False,indent=2));return 1
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except(OSError,ValueError,KeyError)as exc:parser.exit(1,f'Installation refused: {exc}\n')


if __name__=='__main__':
    raise SystemExit(main())
