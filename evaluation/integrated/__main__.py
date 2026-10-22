import argparse,json
from .campaign import create,run_next
from goalpilot.model import ContractError
p=argparse.ArgumentParser();p.add_argument('action',choices=('create','run'));p.add_argument('--output',required=True);p.add_argument('--live',action='store_true');a=p.parse_args()
if a.action=='create':
 m=create(a.output);print(json.dumps({'registered':len(m['order']),'order':[x['mode']for x in m['order']],'seconds':m['seconds_per_trial'],'observed_token_cap':m['observed_campaign_token_cap'],'same_product':m['same_product_source_as_first_study'],'reference_groups':m['preflight']['reference_passed_groups']}))
else:
 if not a.live:raise ContractError('--live required')
 while True:
  r=run_next(a.output)
  if r is None:break
  print(json.dumps({k:r[k]for k in ('id','status','seconds','success','usage','error')}),flush=True)
