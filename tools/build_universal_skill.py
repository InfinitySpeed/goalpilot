"""Package the generalized skill; preserve the exact r2 service control."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OVERLAYS={'SKILL.md':'integrations/native/routed-SKILL.md','scripts/native.py':'integrations/native/native.py',
          'references/native.md':'integrations/native/SKILL.md','references/service.md':'skills/goalpilot-016/SKILL.md'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def build(root=ROOT,*,candidate=False):
    root=Path(root);policy=json.loads((root/'PORTABLE_SKILL.json').read_text())
    native=policy.get('active_native_workflow',policy.get('native_workflow',{}))
    version=native.get('version','1.8.0');adapter=native.get('adapter_version','0.1.0')
    if native.get('status')!='promoted'and not candidate:raise ValueError('Generalized skill has no promotion')
    base=root/'skills/goalpilot-016';manifest=json.loads((base/'MANIFEST.json').read_text())
    if manifest['files']!=policy['measured_files']:raise ValueError('Base control manifest differs')
    for name,value in manifest['files'].items():
        if sha(base/name)!=value:raise ValueError('Changed frozen service control: '+name)
    if native.get('status')=='promoted':
        for name,value in native['source_files'].items():
            if sha(root/name)!=value:raise ValueError('Changed native promotion: '+name)
    with tempfile.TemporaryDirectory()as tmp:
        target=Path(tmp)/'goalpilot'
        shutil.copytree(base,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for name,source in OVERLAYS.items():shutil.copy2(root/source,target/name)
        shutil.copy2(root/'LICENSE',target/'LICENSE')
        files={str(p.relative_to(target)):sha(p)for p in sorted(target.rglob('*'))if p.is_file()and p.name!='MANIFEST.json'}
        manifest.update(skill_version=version,native_adapter_version=adapter,entry_point='scripts/native.py',
                        files=files,measured_runtime_and_skill_parity=False,
                        meter_scope='Native and service routes have separate whole-caller evidence. See docs/GENERALIZATION.md; historical r2 metrics do not describe this changed skill. No cross-host or subscription-quota guarantee.')
        (target/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
        archive=root/('dist/goalpilot-skill-'+version+'.zip');archive.parent.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED)as z:
            for p in sorted(target.rglob('*')):
                if p.is_file():z.write(p,'goalpilot/'+p.relative_to(target).as_posix())
    with zipfile.ZipFile(archive)as z:
        assert z.testzip()is None
        for name,value in files.items():
            if hashlib.sha256(z.read('goalpilot/'+name)).hexdigest()!=value:raise ValueError('Package differs')
    return {'path':str(archive),'skill_version':version,'engine_version':'0.16.0','native_adapter_version':adapter,'files_verified':len(files),'all_hashes_verified':True,'bytes':archive.stat().st_size,'sha256':sha(archive),'model_calls':0}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',action='store_true')
    print(json.dumps(build(candidate=parser.parse_args().candidate),indent=2))
