"""Exercise installed native verification across runtimes, without model calls.

This measures verifier compatibility, NOT agent discovery or model performance.
Missing runtimes are reported as unsupported, never counted as successful.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
HOSTS = ('codex', 'claude-code', 'antigravity', 'hermes', 'generic')


def fixtures():
    return {
        'python': ('app.py', 'print(42)\n', [sys.executable, 'app.py'], None),
        'javascript': ('app.mjs', 'console.log(42);\n', ['node', 'app.mjs'], ['node', '--version']),
        'typescript': ('app.ts', 'const answer: number = 42; console.log(answer);\n', [sys.executable, 'compile_run.py'], ['tsc', '--version']),
        'bash': ('app.sh', 'printf "%s\\n" 42\n', ['bash', 'app.sh'], ['bash', '--version']),
        'sqlite': ('app.sql', 'SELECT 42;\n', [sys.executable, '-c', "import sqlite3,pathlib;print(sqlite3.connect(':memory:').execute(pathlib.Path('app.sql').read_text()).fetchone()[0])"], None),
        'c': ('app.c', '#include <stdio.h>\nint main(void){printf("%d\\n",42);return 0;}\n', [sys.executable, 'compile_run.py'], ['cc', '--version']),
        'java': ('App.java', 'class App {public static void main(String[] args){System.out.println(42);}}\n', ['java', 'App.java'], ['java', '--version']),
        'go': ('app.go', 'package main\nimport "fmt"\nfunc main(){fmt.Println(42)}\n', ['go', 'run', 'app.go'], ['go', 'version']),
    }


def execute(argv, cwd=None, timeout=30):
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding='utf-8', timeout=timeout)


def capability(probe):
    if probe is None:
        return {'ready': True, 'version': platform.python_version()}
    if not shutil.which(probe[0]):
        return {'ready': False, 'reason': 'executable missing: ' + probe[0]}
    try:
        result = execute(probe, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'ready': False, 'reason': str(exc)}
    output = (result.stdout + result.stderr).strip()[:500]
    # /usr/bin/go may be the Go board game rather than the Go compiler.
    ready = result.returncode == 0 and (probe[0] != 'go' or output.startswith('go version go'))
    return {'ready': ready, 'version': output, **({} if ready else {'reason': 'runtime probe failed'})}


def exercise(target, root, stack, fixture):
    repo = root / ('project café 東京 ' + stack)
    repo.mkdir()
    source, good, command, _ = fixture
    (repo / source).write_text(good, encoding='utf-8')
    if stack == 'c':
        (repo / 'compile_run.py').write_text("import pathlib,subprocess,tempfile\nwith tempfile.TemporaryDirectory() as d:\n p=pathlib.Path(d)/'app';subprocess.run(['cc','app.c','-o',str(p)],check=True);subprocess.run([str(p)],check=True)\n", encoding='utf-8')
    if stack == 'typescript':
        (repo / 'compile_run.py').write_text("import pathlib,subprocess,tempfile\nwith tempfile.TemporaryDirectory() as d:\n subprocess.run(['tsc','--target','ES2020','--module','commonjs','--outDir',d,'app.ts'],check=True);subprocess.run(['node',str(pathlib.Path(d)/'app.js')],check=True)\n", encoding='utf-8')
    # The original test checks program behavior, not the compiler's exit status.
    test = "import subprocess\nr=subprocess.run(" + repr(command) + ",capture_output=True,text=True)\nassert r.returncode==0,(r.stdout,r.stderr)\nassert r.stdout.strip()=='42',r.stdout\n"
    (repo / 'test_behavior.py').write_text(test, encoding='utf-8')
    run = root / ('evidence ' + stack)
    goal = 'Preserve the answer 42. Café 東京.'
    cli = [sys.executable, str(target / 'scripts/native.py')]
    def call(*args, expected=0):
        result = execute([*cli, *map(str, args)], timeout=100)
        if result.returncode != expected:
            raise RuntimeError(result.stdout + result.stderr)
        return json.loads(result.stdout)
    call('begin', '--repo', repo, '--run-dir', run, '--goal', goal, '--wall-seconds', '90', '--max-verifications', '2')
    criteria = root / (stack + '-criteria.json')
    criteria.write_text(json.dumps({'checks': [{'id': 'behavior', 'argv': [sys.executable, 'test_behavior.py']}], 'criteria': [{'quote': 'Preserve the answer 42', 'checks': ['behavior']}]}), encoding='utf-8')
    (repo / source).write_text(good.replace('42', '41'), encoding='utf-8')
    failed = call('deliver', run, '--criteria-file', criteria, expected=1)
    if failed['goal_complete'] or failed['checks_passed']:
        raise RuntimeError('Incorrect implementation was accepted')
    (repo / source).write_text(good, encoding='utf-8')
    passed = call('finish', run)
    if not passed['goal_complete'] or passed['attempts'] != 2:
        raise RuntimeError('Correct repair did not preserve the failed attempt')
    cached = call('finish', run)
    (repo / source).write_text(good.replace('42', '43'), encoding='utf-8')
    stale = call('status', run)
    checks = {
        'wrong_answer_rejected': not failed['goal_complete'],
        'correct_repair_verified': passed['goal_complete'],
        'failure_retained': (run / 'attempt-1/result.json').is_file(),
        'verbatim_goal': (run / 'goal.bin').read_bytes() == goal.encode('utf-8'),
        'original_test_unchanged': (run / 'original/test_behavior.py').read_text(encoding='utf-8') == test,
        'unchanged_finish_reused': cached['attempts'] == 2,
        'changed_source_invalidates': stale['status'] == 'stale' and not stale['goal_complete'],
        'no_engine_model_calls': passed['engine_model_calls'] == 0,
    }
    if not all(checks.values()):
        raise RuntimeError(json.dumps(checks))
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hosts', nargs='+', choices=HOSTS, default=list(HOSTS))
    parser.add_argument('--stacks', nargs='+', choices=tuple(fixtures()), default=list(fixtures()))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--require-all', action='store_true', help='Fail when any requested runtime is unavailable')
    args = parser.parse_args()
    started = time.monotonic()
    probes = {stack: capability(fixtures()[stack][3]) for stack in args.stacks}
    rows = []
    with tempfile.TemporaryDirectory(prefix='goalpilot-portability-') as tmp:
        root = Path(tmp)
        for host in args.hosts:
            target = root / host / 'skill'
            installed = execute([sys.executable, str(ROOT / 'install.py'), '--host', host, '--target', str(target)], timeout=60)
            for stack in args.stacks:
                row = {'host_profile': host, 'stack': stack}
                if installed.returncode:
                    row.update(status='failed', error=installed.stdout + installed.stderr)
                elif not probes[stack]['ready']:
                    row.update(status='unsupported', reason=probes[stack].get('reason'))
                else:
                    case_root = root / host / stack
                    case_root.mkdir()
                    try:
                        row.update(status='passed', checks=exercise(target, case_root, stack, fixtures()[stack]))
                    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
                        row.update(status='failed', error=str(exc))
                rows.append(row)
    report = {
        'schema_version': 1, 'scope': 'Installed verifier runtime compatibility; NOT coding-agent performance or automatic discovery',
        'platform': platform.platform(), 'python': platform.python_version(),
        'live_model_calls': 0, 'direct_model_tokens': 0, 'parent_conversation_tokens': 'UNKNOWN', 'seconds': time.monotonic() - started,
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__).resolve(), ROOT / 'install.py', ROOT / 'PORTABLE_SKILL.json', ROOT / 'integrations/native/native.py')},
        'capabilities': probes, 'rows': rows,
        'passed': sum(r['status'] == 'passed' for r in rows),
        'failed': sum(r['status'] == 'failed' for r in rows),
        'unsupported': sum(r['status'] == 'unsupported' for r in rows),
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return int(bool(report['failed'] or args.require_all and report['unsupported']))


if __name__ == '__main__':
    raise SystemExit(main())
