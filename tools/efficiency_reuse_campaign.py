"""Three fresh executions plus an explicitly reused successful historical control."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from efficiency_campaign import hashes,write

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def create(output):
    from evaluation.ambitious.specs import GOALS,SPECS
    from evaluation.ambitious.preflight import run
    ci=json.loads((ROOT/'reports/tests.json').read_text());assert ci['successful']and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==s for p,s in ci['source_fingerprint'].items())
    smoke=json.loads((ROOT/'reports/arithmetic-review-smoke-001/reference-replay-002.json').read_text());assert smoke['review_complete']and smoke['fixed_all_passed']and smoke['original_has_failure']
    assert not output.exists();output.mkdir(parents=True)
    archive=ROOT/'reports/efficiency-live-001';control=archive/'trials/flowdesk-baseline';r=json.loads((control/'record.json').read_text());assert r['success']and r['usage']['usage_complete']
    origins={'baseline':Path('/workspace/goalpilot-baseline'),'candidate':ROOT}
    for mode,origin in origins.items():
        dest=output/'source_snapshot'/mode
        for folder in ('goalpilot','tests'):shutil.copytree(origin/folder,dest/folder,ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT/'evaluation/ambitious',dest/'evaluation/ambitious',ignore=shutil.ignore_patterns('__pycache__'))
        (dest/'evaluation/__init__.py').write_text('')
        shutil.copytree(ROOT/'examples',dest/'examples',ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('validate.py','pyproject.toml'):shutil.copy2(origin/name,dest/name)
        shutil.copy2(ROOT/'tools/efficiency_campaign.py',dest/'worker.py')
    same=all(hashlib.sha256(p.read_bytes()).hexdigest()==hashlib.sha256((archive/'source_snapshot/baseline/goalpilot'/p.name).read_bytes()).hexdigest()for p in(output/'source_snapshot/baseline/goalpilot').glob('*.py'));assert same
    shutil.copytree(control,output/'trials/flowdesk-baseline')
    m={'registered_at':time.time(),'model':'gpt-6.1-sol','versions':{'baseline':'0.5.2','candidate':'0.6.2'},'cases':['flowdesk','stockroom'],'goals':{k:GOALS[k]for k in ('flowdesk','stockroom')},'public_contracts':{k:SPECS[k]for k in ('flowdesk','stockroom')},
    'order':[{'case':c,'mode':mode,'id':c+'-'+mode}for c,mode in [('flowdesk','baseline'),('flowdesk','candidate'),('stockroom','candidate'),('stockroom','baseline')]],
    'seconds_per_trial':900,'max_calls':6,'max_tokens_per_trial':1500000,'observed_campaign_token_cap':6000000,'case_limits':{'flowdesk':{'seconds_per_trial':900,'max_calls':6},'stockroom':{'seconds_per_trial':900,'max_calls':4}},
    'archived_cells':['flowdesk-baseline'],'archived_control':{'source':str(control),'record_sha256':hashlib.sha256((control/'record.json').read_bytes()).hexdigest(),'known_outcome_before_candidate_design':True,'same_product_bytes':same,'selection':'Reuse the earlier successful fully metered0.5.2 control (480s), rather than inflate gains with the later900s blocked partial control. This is explicitly historical, not a new randomized concurrent control. Failed0.6.0/0.6.1 studies and later failed0.5.2 control remain archived and charged as development.','new_research_usage':0},
    'primary_allows_baseline_bounds':True,'primary_rule':'Both0.6.2 candidate goals normally concluded and all26 original independent groups each pass; zero paired correctness/closure regressions. At least20% less aggregate full elapsed time AND raw tokens AND uncached-input+output. Candidates require fully complete meters checked against raw. Baseline partials permit only conservative savings LOWER BOUNDS (baseline true >= known; candidate exact required). No statistical population claim.',
    'design':'One explicitly reused successful historical Flowdesk0.5.2 control plus THREE fresh executions: Flowdesk0.6.2, Stockroom0.6.2 and Stockroom0.5.2. Not four new trials. Same model, original files/contracts, judge, per-case budgets and initial inputs. Flowdesk has900s/6calls in both arms; Stockroom has900s/4calls in both arms to bound research quota. All acceptance generation, fresh arithmetic validation, plumbing repair, coding, actual checks and repairs included. Independent grader never feeds workers; no human steering or injected interruption.',
    'novelty':'Familiar synthetic domains used in failed development studies, not held-out personal goals.0.6.0 and0.6.1 both created correct code but froze defective criteria; both interrupted failed studies remain intact.0.6.2 adds fresh-context arithmetic validation BEFORE implementation/freezing. An exposed-program technical smoke passed; it is not a fresh goal-success trial.',
    'stopping':'Stop between whole trials on candidate incomplete usage (no conservative saving then possible), fatal provider/infrastructure failure, observed6M known raw cap, or paired regression. Never rerun a failed candidate or change sources/criteria mid-study. Keep original planned3fresh/4cells denominator. Baseline incomplete meters are explicit lower bounds; no exact token saving from them.',
    'offline_validation':ci,'preflight':run(),'source_fingerprints':{mode:hashes(output/'source_snapshot'/mode)for mode in origins}}
    write(output/'protocol.json',m);write(output/'preregistered-protocol.json',m)


def run(output):
    m=json.loads((output/'protocol.json').read_text());assert m==json.loads((output/'preregistered-protocol.json').read_text())
    for item in m['order']:
        rows=[json.loads(p.read_text())for p in(output/'trials').glob('*/record.json')]
        if any(r['fatal']or r['mode']=='candidate'and not r['usage']['usage_complete']for r in rows)or sum(r['usage']['total_tokens']for r in rows)>=m['observed_campaign_token_cap']:return
        for case in m['cases']:
            pair={r['mode']:r for r in rows if r['case']==case}
            if len(pair)==2 and(pair['baseline']['success']and not pair['candidate']['success']or pair['baseline']['artifact_success']and not pair['candidate']['artifact_success']):
                write(output/'stopped.json',{'reason':'Preregistered paired regression','planned_fresh_trials':3,'completed_cells':len(rows)});return
        if any(r['id']==item['id']for r in rows):continue
        assert not(output/'trials'/item['id']).exists(),'Uncommitted trial cannot be blindly rerun'
        source=output/'source_snapshot'/item['mode'];assert hashes(source)==m['source_fingerprints'][item['mode']]
        subprocess.run([sys.executable,str(source/'worker.py'),'worker',str(output),item['id'],str(source)],check=True,cwd=source)


if __name__=='__main__':
    output=Path(sys.argv[2]).resolve()
    if sys.argv[1]=='create':create(output)
    elif sys.argv[1]=='run':run(output)
