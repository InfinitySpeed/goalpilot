"""Freeze existing unittest acceptance, exercise it against a disposable worktree.

This is local verification, not inference that existing tests cover the whole goal.
The standalone copy of this file needs only Python stdlib.
"""
from __future__ import annotations
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

IGNORE={'.git','.codex','.aws','.agents','.venv','venv','node_modules','__pycache__','dist','build','.pytest_cache','.mypy_cache','.next','coverage'}


def assertion_count(snapshot):
    """Local routing evidence only; assertion growth does not prove coverage."""
    count=0
    for item in snapshot['files']:
        if not item['path'].startswith('tests/')or not item['path'].endswith('.py'):continue
        try:tree=ast.parse((Path(snapshot['directory'])/item['path']).read_text())
        except (OSError,SyntaxError,UnicodeError):return 0
        count+=sum(isinstance(n,ast.Assert)or isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr.startswith('assert')for n in ast.walk(tree))
    return count


def make_gate(repo, run_dir, snapshot):
    """Return a check only when original bounded copies include unittest tests."""
    entries=[x for x in snapshot['files'] if x['path'].startswith('tests/')]
    candidates=[x for x in entries if Path(x['path']).name.startswith('test') and x['path'].endswith('.py')]
    originals=Path(snapshot['directory'])
    supported=[]
    for item in candidates:
        try:tree=ast.parse((originals/item['path']).read_text())
        except (SyntaxError,UnicodeError):return None
        modules={'unittest'};bases={'TestCase'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                modules.update(a.asname or a.name for a in node.names if a.name=='unittest')
            if isinstance(node,ast.ImportFrom) and node.module=='unittest':
                bases.update(a.asname or a.name for a in node.names if a.name=='TestCase')
        classes=[n for n in ast.walk(tree) if isinstance(n,ast.ClassDef)]
        known=set(bases)
        for _ in classes:
            for cls in classes:
                if any(isinstance(b,ast.Name) and b.id in known or isinstance(b,ast.Attribute) and b.attr=='TestCase' and isinstance(b.value,ast.Name) and b.value.id in modules for b in cls.bases):
                    known.add(cls.name)
        methods=[m for cls in classes if cls.name in known for m in cls.body
                 if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)) and m.name.startswith('test')]
        substantive=any(isinstance(n,ast.Assert) or isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr.startswith('assert') for m in methods for n in ast.walk(m))
        # This runner is unittest-only. Do not interpret pytest assertions as a
        # discoverable suite, or silently claim coverage of a mixed suite.
        if not substantive:return None
        supported.append(item)
    if not supported:return None
    # An incomplete initial test directory cannot be represented as complete.
    actual={str(p.relative_to(repo)) for p in (Path(repo)/'tests').rglob('*')
            if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts}
    if not actual.issubset({x['path'] for x in entries}):return None
    folder=Path(run_dir)/'original-tests';folder.mkdir(exist_ok=True)
    runner=folder/'runner.py';runner.write_bytes(Path(__file__).read_bytes())
    manifest=folder/'gate.json'
    payload={'originals':str(originals),'files':entries,'max_bytes':64000000,'max_entries':4000}
    manifest.write_text(json.dumps(payload,indent=2)+'\n')
    artifacts=[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (runner,manifest)]
    artifacts.extend({'path':str(originals/x['path']),'sha256':x['sha256']} for x in entries)
    return {'check':{'id':'original-tests','description':'Original unittest tests and fixtures still pass against delivered code, even if working tests were weakened',
            'command':[sys.executable,str(runner),str(manifest)],'timeout_seconds':60,'infrastructure_codes':[86]},
            'artifacts':artifacts,'original_test_files':len(supported)}


def run_gate(manifest):
    repo=Path.cwd();data=json.loads(Path(manifest).read_text());used=0;count=0
    with tempfile.TemporaryDirectory(prefix='goalpilot-gate-') as tmp:
        clone=Path(tmp)
        for directory,dirs,names in os.walk(repo,followlinks=False):
            dirs[:]=sorted(d for d in dirs if d not in IGNORE and not (Path(directory)/d).is_symlink())
            count+=len(dirs)+len(names)
            if count>data['max_entries']:raise RuntimeError('Worktree entry limit exceeded')
            for name in sorted(names):
                p=Path(directory)/name
                if p.is_symlink() or not p.is_file():continue
                lower=name.lower()
                if name.startswith('.env') or any(w in lower for w in ('credential','secret','auth.json')):continue
                used+=p.stat().st_size
                if used>data['max_bytes']:raise RuntimeError('Worktree byte limit exceeded')
                target=clone/p.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        for item in data['files']:
            source=Path(data['originals'])/item['path']
            if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest()!=item['sha256']:
                raise RuntimeError('Frozen original test changed')
            target=clone/item['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        code="""import pathlib,sys,unittest
suite=unittest.defaultTestLoader.discover('tests',top_level_dir='.' if pathlib.Path('tests/__init__.py').exists() else None)
if suite.countTestCases()==0:
 print('GOALPILOT_GATE_INFRASTRUCTURE: no tests discovered',file=sys.stderr);sys.exit(86)
result=unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
"""
        return subprocess.call([sys.executable,'-c',code],cwd=clone)


if __name__=='__main__':
    try:code=run_gate(sys.argv[1])
    except Exception as exc:
        print(f'GOALPILOT_GATE_INFRASTRUCTURE: {type(exc).__name__}: {exc}',file=sys.stderr);code=86
    sys.exit(code)
