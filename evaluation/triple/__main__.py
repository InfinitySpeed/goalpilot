import argparse,json
from .campaign import create,run_next
from .report import report
from goalpilot.model import ContractError

p=argparse.ArgumentParser();p.add_argument('action',choices=('create','run','report'));p.add_argument('--output',required=True);p.add_argument('--live',action='store_true');a=p.parse_args()
if a.action=='create':
 m=create(a.output);print(json.dumps({'trials':len(m['order']),'budget_seconds':m['seconds_per_trial'],'observed_token_cap':m['campaign_observed_token_cap'],'preflight':m['preflight']},indent=2))
elif a.action=='report':
 r=report(a.output);print(json.dumps({k:r[k]for k in ('complete','groups','quality_wins','quality_losses','savings_percent','joint_preregistered_criterion_met')},indent=2))
else:
 if not a.live:raise ContractError('--live required; uses authenticated Codex')
 while True:
  r=run_next(a.output)
  if r is None:break
  print(json.dumps({k:r[k]for k in ('id','status','seconds','success','usage','error')},ensure_ascii=False),flush=True)
