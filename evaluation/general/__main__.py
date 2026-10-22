import argparse
import json
from pathlib import Path
from .campaign import plan,run_next,recover
from .report import write


def main():
    p=argparse.ArgumentParser(description='Autonomous paired evaluation; no calls unless run --live.')
    sub=p.add_subparsers(dest='command',required=True)
    create=sub.add_parser('create');create.add_argument('--output',type=Path,required=True);create.add_argument('--seconds',type=int,default=600);create.add_argument('--repeats',type=int,default=2);create.add_argument('--model',default='gpt-6.1-sol')
    run=sub.add_parser('run');run.add_argument('--output',type=Path,required=True);run.add_argument('--live',action='store_true')
    recover_parser=sub.add_parser('recover');recover_parser.add_argument('--output',type=Path,required=True);recover_parser.add_argument('--reason',required=True)
    report=sub.add_parser('report');report.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.command=='create':
        x=plan(args.output,args.seconds,args.repeats,args.model);print(json.dumps({'planned_trials':len(x['order']),'seconds_per_trial':args.seconds}));write(args.output)
    elif args.command=='run':
        x=run_next(args.output,live=args.live);r=write(args.output)
        print(json.dumps({k:v for k,v in (x or {}).items() if k not in ('calls','checks')},ensure_ascii=False))
        if x and x.get('fatal'):return 2
    elif args.command=='recover':recover(args.output,args.reason);write(args.output)
    else:
        r=write(args.output);print(json.dumps({k:v for k,v in r.items() if k!='records'},indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
