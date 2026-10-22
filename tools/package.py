"""Build a source/evidence archive with content hashes and no symlink traversal."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SKIP={'__pycache__','.git','.venv','venv','.pytest_cache','node_modules'}


def main():
    files=[]
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT)
        if any(x in SKIP or x.endswith('.egg-info') for x in rel.parts):continue
        if p.is_symlink() or not p.is_file() or p.suffix=='.pyc':continue
        name=p.name.lower()
        if name.startswith('.env') or name in ('auth.json','credentials.json','id_rsa','id_ed25519'):continue
        if p.suffix.lower() in ('.pem','.key'):continue
        if rel.as_posix()=='MANIFEST.json':continue
        files.append((p,rel.as_posix()))
    manifest={'version':__import__('goalpilot').__version__,'files':[
        {'path':rel,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p,rel in files],
        'note':'Source and retained evidence. Historical tokens in explicit simulated replays are not new API consumption. Symlinks, caches and conventional credential files excluded. This manifest excludes itself.'}
    dest=ROOT.parent/'goalpilot.zip';manifest_bytes=(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode()
    (ROOT/'MANIFEST.json').write_bytes(manifest_bytes)
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p,rel in files:z.write(p,'goalpilot/'+rel)
        z.writestr('goalpilot/MANIFEST.json',manifest_bytes)
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None
        for row in manifest['files']:
            assert hashlib.sha256(z.read('goalpilot/'+row['path'])).hexdigest()==row['sha256'],row['path']
    result={'path':str(dest),'bytes':dest.stat().st_size,'files':len(files)+1,
            'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'all_file_hashes_verified':True}
    (ROOT.parent/'goalpilot-release.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
