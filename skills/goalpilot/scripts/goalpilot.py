#!/usr/bin/env python3
"""Forward to the byte-identical embedded CLI; goal files avoid shell interpolation."""
from pathlib import Path
import hashlib
import json
import sys


def arguments(argv):
    args=list(argv)
    if not args or args[0]!='go':return args
    end=args.index('--')if '--'in args else len(args)
    positions=[i for i,a in enumerate(args[:end])if a=='--goal-file']
    if not positions:return args
    if len(positions)!=1:raise ValueError('Supply --goal-file exactly once')
    i=positions[0]
    if i+1>=end:raise ValueError('--goal-file requires a UTF-8 file path')
    goal=Path(args[i+1]).read_bytes().decode('utf-8')
    del args[i:i+2]
    # The goal is one argv value, even when it contains quotes, newlines or options.
    if '--'not in args:args.append('--')
    args.append(goal)
    return args


def main(argv=None):
    try:args=arguments(sys.argv[1:]if argv is None else argv)
    except (OSError,UnicodeError,ValueError)as exc:
        print(f'GoalPilot skill: {exc}',file=sys.stderr);return 2
    root=Path(__file__).resolve().parents[1]
    runtime=root/'runtime'
    try:
        manifest=json.loads((root/'MANIFEST.json').read_text())
        expected=manifest['engine']['files']
        actual={str(p.relative_to(runtime/'goalpilot')):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((runtime/'goalpilot').glob('*.py'))}
        if actual!=expected or not actual:raise ValueError('Embedded engine differs from its verified manifest')
    except (OSError,ValueError,KeyError)as exc:
        print(f'GoalPilot skill: invalid or missing bundled runtime: {exc}',file=sys.stderr);return 2
    sys.path.insert(0,str(runtime))
    from goalpilot.cli import main as run
    return run(args)


if __name__=='__main__':raise SystemExit(main())
