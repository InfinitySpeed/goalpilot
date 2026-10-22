import argparse,json
from .campaign import create,run_next
from .report import report
from goalpilot.model import ContractError
p=argparse.ArgumentParser();p.add_argument('action',choices=['create','run','report']);p.add_argument('--output',required=True);p.add_argument('--live',action='store_true');a=p.parse_args()
if a.action=='create':
    m=create(a.output);print(json.dumps({'planned_runs':len(m['order']),'seconds_per_trial':m['seconds_per_trial'],'observed_campaign_token_cap':m['campaign_observed_token_cap'],'preflight':m['preflight']},indent=2))
elif a.action=='report':
    r=report(a.output);print(json.dumps({k:r[k]for k in('complete','primary_completion_advantage_observed','groups','quality_wins','quality_losses')},indent=2))
else:
    if not a.live:raise ContractError('--live required: authenticated Codex usage')
    while True:
        r=run_next(a.output)
        if r is None:break
        print(json.dumps({k:r[k]for k in('id','status','success','seconds','usage','error')}),flush=True)
