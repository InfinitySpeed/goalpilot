#!/usr/bin/env python3
"""Install the self-contained skill locally, without pip, login or inference."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import uuid


def validate(root):
    root=Path(root)
    manifest=json.loads((root/'MANIFEST.json').read_text())
    if manifest.get('package')!='goalpilot-codex-skill':raise ValueError('Not a GoalPilot skill bundle')
    for name,sha in manifest['files'].items():
        rel=Path(name)
        if rel.is_absolute()or '..'in rel.parts:raise ValueError('Invalid manifest path')
        path=root/rel
        if path.is_symlink()or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError(f'Invalid bundle file: {name}')
    for directory in root.rglob('*'):
        if directory.is_symlink():raise ValueError('Symlink in skill bundle')
    return manifest


def install(source,target):
    source=Path(source).resolve();target=Path(target).expanduser().absolute()
    manifest=validate(source)
    if target.is_symlink():raise ValueError('Refusing to replace a symlink')
    if target.exists():
        if source==target.resolve():return {'path':str(target),'already_installed':True,'engine_version':manifest['engine']['version']}
        # Only replace this package. Never overwrite an unrelated user skill.
        previous=json.loads((target/'MANIFEST.json').read_text())
        if previous.get('package')!='goalpilot-codex-skill':raise ValueError('Destination belongs to another skill')
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.goalpilot-install-',dir=target.parent)as tmp:
        staged=Path(tmp)/'goalpilot'
        shutil.copytree(source,staged,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        validate(staged)
        backup=target.with_name('.goalpilot-backup-'+uuid.uuid4().hex)
        had_previous=target.exists()
        if had_previous:target.rename(backup)
        try:
            staged.rename(target);validate(target)
        except BaseException:
            if target.exists():shutil.rmtree(target)
            if had_previous:backup.rename(target)
            raise
        if had_previous:shutil.rmtree(backup)
    return {'path':str(target),'already_installed':False,'engine_version':manifest['engine']['version']}


def main():
    parser=argparse.ArgumentParser(description='Installer le skill Codex GoalPilot, sans dépendance réseau')
    parser.add_argument('--target',type=Path,default=Path.home()/'.agents/skills/goalpilot')
    args=parser.parse_args()
    try:result=install(Path(__file__).resolve().parents[1],args.target)
    except (OSError,ValueError,KeyError)as exc:parser.exit(1,f'Installation refusée : {exc}\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
