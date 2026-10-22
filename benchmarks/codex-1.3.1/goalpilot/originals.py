"""Bounded, unexecuted pre-build copies for data-preservation comparisons."""
import hashlib
import os
from pathlib import Path
from .dossier import IGNORE
from .engine import atomic_json

# Ordinary project metadata must participate in the snapshot, rather than make
# an otherwise supported repository impossible to close. Other hidden files
# retain the conservative exclusion policy (notably .env and auth material).
PROJECT_METADATA = frozenset({'.gitignore', '.gitattributes', '.editorconfig',
                              '.python-version', '.dockerignore'})


def capture(repo, destination, *, max_files=128, max_bytes=16000000, max_file_bytes=4000000, max_entries=4000):
    repo,destination=Path(repo),Path(destination)
    files=[];omitted=[];used=0;visited=0;complete=True
    for root,dirs,names in os.walk(repo,followlinks=False):
        dirs[:]=sorted(d for d in dirs if d not in IGNORE and not d.startswith('.') and not (Path(root)/d).is_symlink())
        visited+=len(dirs)+len(names)
        if visited>max_entries:complete=False;break
        for name in sorted(names):
            path=Path(root)/name;relative=str(path.relative_to(repo));lower=name.lower()
            if (path.is_symlink() or not path.is_file() or name.startswith('.') and name not in PROJECT_METADATA or
                any(x in lower for x in ('credential','secret','auth.json','id_rsa','id_ed25519')) or
                path.suffix.lower() in ('.pem','.key')):
                omitted.append(relative);continue
            if len(files)>=max_files or used>=max_bytes:
                complete=False;break
            limit=min(max_file_bytes,max_bytes-used)
            with path.open('rb') as stream:data=stream.read(limit+1)
            if len(data)>limit:
                complete=False;omitted.append(relative);continue
            target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            files.append({'path':relative,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
            used+=len(data)
        if len(files)>=max_files or used>=max_bytes:complete=False;break
    inventory={'directory':str(destination.resolve()),'files':files,'omitted':omitted,
               'within_limits':complete,'bytes':used,
               'note':'Bounded copies of initial local files, including ordinary project metadata. Excludes conventional credentials, other hidden paths, symlinks and caches. Not a consistent backup of concurrently modified databases.'}
    atomic_json(destination.parent/'original-inventory.json',inventory)
    return inventory


def intact(snapshot):
    if not snapshot:
        return True
    try:
        root=Path(snapshot['directory'])
        return all((p:=root/x['path']).is_file() and not p.is_symlink() and
                   hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256'] for x in snapshot['files'])
    except OSError:
        return False
