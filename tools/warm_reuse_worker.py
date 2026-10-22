"""Secondary exact-repeat filesystem experiment: no model process may be launched."""
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from goalpilot.engine import atomic_json,token_totals
from goalpilot.reuse import run_cached_finish
from evaluation.ambitious.cases import materialize
from evaluation.ambitious.judge import evaluate


def run(out):
    m=json.loads((out/'protocol.json').read_text());rows=[]
    for case in m['cases']:
        trial=out/'trials'/(case+'-goalpilot');coldpath=trial/'record.json'
        cold=json.loads(coldpath.read_text())if coldpath.exists()else None
        goal=m['goals'][case]+'''\nFollow all original README contracts, finish every workflow, preserve data, resolve reversible ambiguities autonomously. Test meaningful public behavior. No human steering, external services, deployment or credentials. Work only in this repository; do not read benchmark/evaluation sources, references, sibling trials or protocol. Do not launch other agents/model sessions or nested Codex commands. Give a factual handoff.'''
        for repeat in range(1,4):
            ident=f'{case}-repeat-{repeat}';dest=out/'warm'/ident
            assert not dest.exists(),'Never overwrite a failed or interrupted repeat'
            dest.mkdir(parents=True);row={'id':ident,'case':case,'repeat':repeat,'planned':True,'executed':False,'success':False}
            if cold and cold['success']:
                repo=materialize(out/'warm-repos'/ident,case);launches=[];error=None
                import subprocess
                real_popen=subprocess.Popen
                def guarded(args,*a,**kw):
                    argv=args if isinstance(args,list)else [args]
                    launches.append([str(x)for x in argv])
                    if any(Path(str(x)).name in ('codex','claude','gemini','aider')for x in argv):raise AssertionError('Model process forbidden in warm study')
                    return real_popen(args,*a,**kw)
                start=time.monotonic();state=None
                try:
                    with patch('goalpilot.rpc.AppServerAdapter.execute',side_effect=AssertionError('No model call permitted')),patch('subprocess.Popen',side_effect=guarded):
                        state=run_cached_finish(goal,repo,dest/'run',cache=trial/'isolated-cache',wall_seconds=900,max_calls=6,max_tokens=m['raw_token_soft_cap_per_trial'],model=m['model'],audit_policy='on-interruption',review_context='local',initial_effort='low',compact_delivery=True)
                except Exception as exc:error=f'{type(exc).__name__}: {exc}'
                seconds=time.monotonic()-start
                judgments=[j for seed in (90173,470117)for j in evaluate(case,repo,seed)]
                correct=len(judgments)==26 and all(j['passed']for j in judgments)
                row.update({'executed':True,'seconds':seconds,'status':state['status']if state else 'incomplete','reuse_hit':bool(state and state.get('reuse',{}).get('hit')),
                            'usage':state['usage']if state else None,'model_calls':len(state['calls'])if state else None,'process_launches':launches,
                            'error':error,'artifact_success':correct,'judgments':judgments,
                            'success':bool(state and state['status']=='scope_passed'and state.get('reuse',{}).get('hit')and not state['calls']and correct),
                            'cache_key':state.get('reuse',{}).get('key')if state else None})
            else:row['reason']='Cold learning did not normally and correctly close; repeat unexecuted'
            atomic_json(dest/'record.json',row);rows.append(row)
    result={'planned':6,'executed':sum(r['executed']for r in rows),'correct_closed':sum(r['success']for r in rows),
            'model_calls':sum(r.get('model_calls')or 0 for r in rows),'rows':rows,
            'quota_claim':'A verified cache hit launches no model inference, hence zero Codex model quota for that repeat. Learning and development costs are separate and nonzero. Unchanged exact request only; no claim for novel/changed goals.',
            'time_comparisons':{},'amortization':{}}
    import math
    for case in m['cases']:
        selected=[r for r in rows if r['case']==case and r['success']]
        if len(selected)!=3:continue
        cold=json.loads((out/'trials'/(case+'-goalpilot')/'record.json').read_text());native=json.loads((out/'trials'/(case+'-native_goal')/'record.json').read_text())
        avg=sum(r['seconds']for r in selected)/3
        result['time_comparisons'][case]={'mean_repeat_seconds':avg,'cold_goalpilot_seconds':cold['seconds'],'historical_native_seconds':native['seconds'],
             'saving_vs_cold_goalpilot_percent':100*(1-avg/cold['seconds']),'saving_vs_historical_native_percent':100*(1-avg/native['seconds'])}
        result['amortization'][case]={'definition':'n identical requests, one measured new cold learning plus n-1 repeats, compared with n historical native executions; hypothetical repeated native cost, not new native runs.',
              'minimum_requests_for_time_win':max(1,math.floor((cold['seconds']-avg)/(native['seconds']-avg))+1),
              'learning_raw_tokens':cold['usage']['total_tokens'],'learning_output_tokens':cold['usage']['output_tokens'],
              'learning_uncached_tokens':cold['usage']['uncached_tokens'],
              'minimum_requests_for_raw_win':cold['usage']['total_tokens']//native['usage']['total_tokens']+1,
              'minimum_requests_for_output_win':cold['usage']['output_tokens']//native['usage']['output_tokens']+1,
              'minimum_requests_for_uncached_win':cold['usage']['uncached_tokens']//native['usage']['uncached_tokens']+1}
    atomic_json(out/'warm-analysis.json',result)
    print(json.dumps({k:v for k,v in result.items()if k!='rows'},indent=2))


if __name__=='__main__':run(Path(sys.argv[1]).resolve())
