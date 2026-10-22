#!/usr/bin/env python3
"""Run the shared local engine without inheriting another host's Codex hooks."""
import os
from pathlib import Path
import runpy
import sys


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('--help', '-h'):
        print('GoalPilot local session adapter\n'
              'Usage: python3 host.py session {start,check,finish,status,submit,verify,repair} ...\n'
              'No Codex executable, host hook setup or model calls are required.')
        return 0
    if args[0] != 'session':
        print('This adapter runs local session commands only. Use: host.py session --help', file=sys.stderr)
        return 2
    os.environ.pop('CODEX_THREAD_ID', None)
    launcher = Path(__file__).resolve().with_name('goalpilot.py')
    sys.argv = [str(launcher), *args]
    runpy.run_path(str(launcher), run_name='__main__')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
