"""Run remaining frozen trials serially; stop on access failure or lost worker."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from evaluation.general.campaign import run_next
from evaluation.general.report import write


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.live:parser.error('--live required: consumes the connected Codex account')
    while True:
        result=run_next(args.output,live=True)
        report=write(args.output)
        if result is None:
            print(json.dumps({'status':'finished','recorded_trials':report['recorded_trials']},ensure_ascii=False),flush=True);return 0
        print(json.dumps({key:result[key] for key in ('id','status','seconds','autonomous_success','artifact_success','blocker_resolved','new_agent_turns','usage','fatal')},ensure_ascii=False),flush=True)
        if result['fatal']:
            print('Provider/transport unavailable; stopping without retries',flush=True);return 2


if __name__=='__main__':raise SystemExit(main())
