"""Two fresh compact-context trials against both successful0.6.2 controls."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from efficiency_campaign import hashes,write

ROOT=Path(__file__).resolve().parents[1]


def create(output):
    previous=ROOT/'reports/efficiency-live-003';old=json.loads((previous/'protocol.json').read_text())
    candidate=Path('/workspace/goalpilot-063');ci=json.loads((candidate/'reports/tests.json').read_text())
    assert ci['successful']and all(hashlib.sha256((candidate/p).read_bytes()).hexdigest()==sha for p,sha in ci['source_fingerprint'].items())
    assert not output.exists();output.mkdir(parents=True)
    origins={'baseline':previous/'source_snapshot/candidate','candidate':candidate}
    for mode,origin in origins.items():
        dest=output/'source_snapshot'/mode
        for folder in ('goalpilot','tests'):shutil.copytree(origin/folder,dest/folder,ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(previous/'source_snapshot/candidate/evaluation',dest/'evaluation',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT/'examples',dest/'examples',ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('validate.py','pyproject.toml'):shutil.copy2(origin/name,dest/name)
        shutil.copy2(ROOT/'tools/efficiency_campaign.py',dest/'worker.py')
    archived=[]
    for case in old['cases']:
        source=previous/'trials'/(case+'-candidate');original=json.loads((source/'record.json').read_text());assert original['success']and original['usage']['usage_complete']
        dest=output/'trials'/(case+'-baseline');shutil.copytree(source,dest);shutil.copy2(source/'record.json',dest/'archived-original-record.json')
        derived={**original,'id':case+'-baseline','mode':'baseline','archived_original':str(source/'record.json')}
        write(dest/'record.json',derived);archived.append({'case':case,'source':str(source),'original_record_sha256':hashlib.sha256((source/'record.json').read_bytes()).hexdigest(),'source_product':'0.6.2','same_initial_bytes_required':True,'new_research_tokens':0})
    m={'registered_at':time.time(),'model':old['model'],'versions':{'baseline':'0.6.2','candidate':'0.6.3'},'cases':old['cases'],'goals':old['goals'],'public_contracts':old['public_contracts'],
    'order':[{'case':case,'mode':mode,'id':case+'-'+mode}for case in old['cases']for mode in ('baseline','candidate')],
    'seconds_per_trial':900,'max_calls':6,'max_tokens_per_trial':1500000,'observed_campaign_token_cap':4000000,'case_limits':old['case_limits'],
    'archived_cells':[case+'-baseline'for case in old['cases']],'archived_controls':archived,
    'primary_allows_baseline_bounds':False,'primary_rule':'Complete both planned NEW0.6.3 executions. Each must normally conclude and pass all26 independent behavioral groups; preserve the observed2/2 successful0.6.2 closure with no artifact regression. At least20% less aggregate full workflow time AND raw input+output AND uncached-input+output. All calls need complete audited meters for exact token claim. Reused controls have complete meters. No population/statistical significance claim.',
    'design':'TWO fresh0.6.3 executions against TWO explicitly reused successful0.6.2 controls from003 (outcomes known during development). Not four fresh/randomized contemporaneous trials. Same initial file bytes, public contracts, judge, model and per-case budgets. Flow900s6calls, Stock900s4calls in both versions. Candidate freezes a tested generic stdlib helper module for local JSONL/HTTP/dispatch/rejections and generates shorter business probes; the builder gets check commands/requirements and reads only failing probes, avoiding repeated full test code in every model step. Independent arithmetic validation and original tests remain, and all preparation/repair/coding costs included. Judge never feeds model. Sources/design fixed before either0.6.3 outcome.',
    'novelty':'Familiar synthetic domains used for development; not held-out personal tasks.0.6.0/0.6.1 verifier failures retained;0.6.2 already delivers both correct goals. This incremental study tests whether shorter context and trusted generic plumbing save resources while keeping that closure. It does not reuse or edit0.6.2 acceptance scripts to score the candidate: new cold acceptance generation, validation and coding are all measured.',
    'stopping':'Stop between trials on candidate incomplete metering, fatal provider/infrastructure failure, any paired correctness/closure regression or observed4M known raw cap. Never repeat a failed candidate, alter original oracle/public contracts or tune code after an outcome. Keep planned2fresh/4comparison-cell denominator. Partial usage is a lower bound, never exact savings.',
    'offline_validation':ci,'preflight':old['preflight'],'preflight_reused_with_identical_judge':'Same unchanged evaluation/ambitious bytes as003; references/mutants already validated. New local helper semantics tested in166-test CI, including real localhost and subprocess cleanup.',
    'source_fingerprints':{mode:hashes(output/'source_snapshot'/mode)for mode in origins}}
    write(output/'protocol.json',m);write(output/'preregistered-protocol.json',m)


def run(output):
    m=json.loads((output/'protocol.json').read_text());assert m==json.loads((output/'preregistered-protocol.json').read_text())
    for item in m['order']:
        rows=[json.loads(p.read_text())for p in(output/'trials').glob('*/record.json')]
        if any(r['fatal']or r['mode']=='candidate'and not r['usage']['usage_complete']for r in rows)or sum(r['usage']['total_tokens']for r in rows)>=m['observed_campaign_token_cap']:return
        for case in m['cases']:
            pair={r['mode']:r for r in rows if r['case']==case}
            if len(pair)==2 and (not pair['candidate']['success']or pair['baseline']['artifact_success']and not pair['candidate']['artifact_success']):
                write(output/'stopped.json',{'reason':'Preregistered paired regression','planned_new':2,'completed_cells':len(rows)});return
        if any(r['id']==item['id']for r in rows):continue
        assert not(output/'trials'/item['id']).exists(),'Never rerun uncommitted candidate'
        source=output/'source_snapshot'/item['mode'];assert hashes(source)==m['source_fingerprints'][item['mode']]
        subprocess.run([sys.executable,str(source/'worker.py'),'worker',str(output),item['id'],str(source)],check=True,cwd=source)


if __name__=='__main__':
    output=Path(sys.argv[2]).resolve()
    if sys.argv[1]=='create':create(output)
    elif sys.argv[1]=='run':run(output)
