"""Two fresh one-pass candidates, both explicitly archived native controls."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from efficiency_campaign import hashes,write

ROOT=Path(__file__).resolve().parents[1]


def create(out):
    old=ROOT/'reports/quota-native-live-001'
    prior=json.loads((old/'analysis.json').read_text())
    assert prior['complete']and prior['integrity_verified']and not prior['joint_20_percent_target_met']
    last=json.loads((ROOT/'reports/quota-native-live-003/analysis.json').read_text());assert last['complete']and last['integrity_verified']and not last['joint_20_percent_target_met']
    interrupted=json.loads((ROOT/'reports/quota-native-live-004/infrastructure-interruption.json').read_text())
    assert interrupted['not_a_positive_resource_or_normal_closure_trial']
    ci=json.loads((ROOT/'reports/tests.json').read_text())
    assert ci['successful']and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==s for p,s in ci['source_fingerprint'].items())
    assert not out.exists();out.mkdir(parents=True)
    snap=out/'source_snapshot'
    for folder in ('goalpilot','tests','evaluation','examples'):
        shutil.copytree(ROOT/folder,snap/folder,ignore=shutil.ignore_patterns('__pycache__'))
    (snap/'tools').mkdir()
    for name in ('local_worker.py','audit_single_native.py'):
        shutil.copy2(ROOT/'tools'/name,snap/'tools'/name)
    for name in ('pyproject.toml','validate.py'):shutil.copy2(ROOT/name,snap/name)
    m=json.loads((old/'protocol.json').read_text())
    controls={}
    for case in m['cases']:
        ident=case+'-native_goal';source=old/'trials'/ident
        row=json.loads((source/'record.json').read_text())
        assert row['artifact_success']and row['usage']['usage_complete']
        shutil.copytree(source,out/'trials'/ident)
        controls[ident]={'source':str(source),'record_sha256':hashlib.sha256((source/'record.json').read_bytes()).hexdigest(),
                         'source_protocol_sha256':hashlib.sha256((old/'preregistered-protocol.json').read_bytes()).hexdigest(),
                         'result_known_before_candidate_design':True,'new_tokens_charged_here':0}
    m.update({'registered_at':time.time(),'product_version':'0.8.0','source_fingerprint':hashes(snap),
              'offline_validation':ci,'archived_controls':controls,'planned_fresh_executions':2,
              'previous_stage_new_raw_tokens':prior['new_known_raw_tokens']+json.loads((ROOT/'reports/quota-native-live-002/analysis.json').read_text())['new_known_raw_tokens']+last['new_known_raw_tokens'],
              'conditional_plan':json.loads((ROOT/'reports/quota-next-plan.json').read_text()),
              'review_optimization':'Local verification first. Default-effort builder strengthens project unittest tests and proposes executable checks in one turn. Original tests are frozen before coding; strengthened tests are frozen AFTER delivery and before repair. Broad goals need assertion growth and a supported immutable unittest gate, otherwise independent post-build audit. No independent pre-build acceptance claimed. Original independent research judge remains unchanged and hidden.',
              'design':'Both historical native controls from previous fully retained0.7.0 study plus TWO NEW0.8.0 candidates. No cherry-picking native controls, native reruns, failed candidate reruns or judge feedback. Original contracts/judge and900s/6calls candidate budget unchanged. Familiar cases and known historical controls limit inference.',
              'primary_rule':'Both new candidates normally closed and correct26/26 each, preserving0.7.0 closure2/2. No artifact regression against native. >=20% aggregate savings versus archived native controls on full seconds AND raw AND uncached. Fully audited counters required. Incomplete study cannot pass. No exact subscription-quota or population claim.',
              'stopping':'Stop on first candidate not fully correct and normally closed, fatal or partial meter, or observed1M NEW raw tokens in this study at whole-trial boundaries. Never rerun failures. Keep planned2 fresh denominator. Historical controls excluded from new research costs.'})
    m['previous_failure'] = 'quota-native-live-002: invalid generated Python quote before freeze, no builder ran, original1/2new planned denominator retained;20290new raw tokens. No trial rerun.'
    m['formatting_repair'] = '0.7.2 locally normalizes ONLY syntactically invalid NUMBER+stray quote+closing punctuation, preserving numeric token text, at most4quote deletions and only if whole result compiles. Valid programs unchanged. Raw programs/receipts retained before freeze; unknown syntax still fails closed. Recovered exposed-program compile smoke is NOT a fresh utility trial.'
    m['new_study_budget_justification']='Prior studies001-003 are complete, retained and used2850458new raw tokens under their3M observed cap. Structural local-verification redesign gets a NEW bounded1M observed raw budget, not a retroactive extension or modification of earlier protocols. Only2new candidates, both native controls reused without new research charge.'
    m['observed_campaign_token_cap']=1000000
    m['legacy_formatting_repair']=m.pop('formatting_repair')
    prior_protocol=json.loads((ROOT/'reports/quota-native-live-004/protocol.json').read_text())
    assert m['source_fingerprint']==prior_protocol['source_fingerprint'],'Exact same0.8source required after infrastructure failure'
    m['interrupted_attempt']=interrupted
    m['interrupted_stage004_known_raw_tokens']=interrupted['known_raw_tokens_lower_bound']
    m['same_exact_source_as_interrupted_attempt']=True
    m['new_study_budget_justification']='Study004 was externally interrupted by an environment restart before its final turn; raw66548known lower bound, final usage and elapsed unknown. It remains an incomplete infrastructure failure, not a success. Study005 has2new candidates, exact same frozen0.8source, original contracts and unchanged hidden judge;2native controls from001reused. No interrupted result reused as normal completion or exact cost. Shared0.8observed1M new raw cap across004+005 uses known interrupted usage as a lower bound; unknown consumption is not zero and a hard actual cap cannot be guaranteed.'
    m['confidence_tradeoff']='Delivery tests come from the builder, not an independent designer. Freezing prevents repair-time weakening but does not prove semantic completeness. Assertion growth is a routing heuristic, not coverage proof. External26group judge is unchanged and never feeds the builder.'
    m['prior_stage003_savings']=last['savings_percent']
    write(out/'protocol.json',m);write(out/'preregistered-protocol.json',m)
    print('REGISTERED',out,flush=True)


def run(out):
    m=json.loads((out/'protocol.json').read_text());assert m==json.loads((out/'preregistered-protocol.json').read_text())
    for case in m['cases']:
        rows=[json.loads(p.read_text())for p in(out/'trials').glob('*/record.json')]
        candidates=[r for r in rows if r['mode']=='goalpilot']
        if any(not r['success']or r['fatal']or not r['usage']['usage_complete']for r in candidates):
            write(out/'stopped.json',{'reason':'Preregistered candidate closure/correctness/meter futility','planned_fresh':2,'completed_fresh':len(candidates)});break
        if m['interrupted_stage004_known_raw_tokens']+sum(r['usage']['total_tokens']for r in candidates)>=1000000:
            write(out/'stopped.json',{'reason':'Shared observed1M known-new raw cap across0.8studies004+005','planned_fresh':2,'completed_fresh':len(candidates)});break
        ident=case+'-goalpilot'
        if any(r['id']==ident for r in rows):continue
        assert hashes(out/'source_snapshot')==m['source_fingerprint']
        subprocess.run([sys.executable,str(out/'source_snapshot/tools/local_worker.py'),'worker',str(out),ident],check=True,cwd=out/'source_snapshot')
    subprocess.run([sys.executable,str(out/'source_snapshot/tools/local_worker.py'),'report',str(out)],check=True,cwd=out/'source_snapshot')


if __name__=='__main__':
    {'create':create,'run':run}[sys.argv[1]](Path(sys.argv[2]).resolve())
