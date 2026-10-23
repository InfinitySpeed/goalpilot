"""Package the versioned 0.16.0 in-session skill without altering its frozen engine."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def build(root=ROOT):
    root=Path(root);skill=root/'skills/goalpilot-016'
    manifest_path=skill/'MANIFEST.json';manifest=json.loads(manifest_path.read_text())
    promoted=json.loads((root/'PROMOTED_ENGINE.json').read_text())
    expected={Path(p).name:h for p,h in promoted['source_hashes'].items()}
    actual={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in (skill/'runtime/goalpilot').glob('*.py')}
    if actual!=expected or manifest['engine']['files']!=expected:
        raise ValueError('Candidate must contain the exact frozen promoted engine')
    files={str(p.relative_to(skill)):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted(skill.rglob('*'))if p.is_file()and'__pycache__'not in p.parts
           and p.suffix!='.pyc'and p!=manifest_path}
    policy_path=root/'PORTABLE_SKILL.json'
    if policy_path.is_file():
        policy=json.loads(policy_path.read_text())
        if policy.get('status')=='promoted' and files!=policy['measured_files']:
            raise ValueError('Promoted skill differs from the measured bundle; new evidence is required')
    manifest['files']=files
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    archive=root/'dist/goalpilot-skill-1.7.0.zip';archive.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED)as z:
        for p in sorted(skill.rglob('*')):
            if p.is_file()and'__pycache__'not in p.parts and p.suffix!='.pyc':
                z.write(p,'goalpilot/'+str(p.relative_to(skill)))
    with zipfile.ZipFile(archive)as z:
        if z.testzip()is not None:raise ValueError('Corrupt archive')
        for p,h in files.items():
            if hashlib.sha256(z.read('goalpilot/'+p)).hexdigest()!=h:raise ValueError('Archive differs')
    return {'skill_version':manifest['skill_version'],'engine_version':manifest['engine']['version'],
            'files_verified':len(files),'archive_bytes':archive.stat().st_size,
            'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'model_calls':0}


if __name__=='__main__':print(json.dumps(build(),indent=2))
