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
    ci=json.loads((ROOT/'reports/tests.json').read_text())
    assert ci['successful']and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==s for p,s in ci['source_fingerprint'].items())
    assert not out.exists();out.mkdir(parents=True)
    snap=out/'source_snapshot'
    for folder in ('goalpilot','tests','evaluation','examples'):
        shutil.copytree(ROOT/folder,snap/folder,ignore=shutil.ignore_patterns('__pycache__'))
    (snap/'tools').mkdir()
    for name in ('onepass_worker.py','audit_single_native.py'):
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
    m.update({'registered_at':time.time(),'product_version':'0.7.1','source_fingerprint':hashes(snap),
              'offline_validation':ci,'archived_controls':controls,'planned_fresh_executions':2,
              'previous_stage_new_raw_tokens':prior['new_known_raw_tokens'],
              'conditional_plan':json.loads((ROOT/'reports/quota-next-plan.json').read_text()),
              'review_optimization':'ONE independent pre-build designer turn, low effort, with arithmetic self-check inside its generation. No separate arithmetic-review call or fresh arithmetic reviewer. Separate default-effort builder still receives complete SHA-frozen probes and original tests. All generated assertions remain immutable after freezing.',
              'design':'Both historical native controls from previous fully retained0.7.0 study plus TWO NEW0.7.1 candidates. No cherry-picking native controls, native reruns, failed candidate reruns or judge feedback. Original contracts/judge and900s/6calls candidate budget unchanged. Familiar cases and known historical controls limit inference.',
              'primary_rule':'Both new candidates normally closed and correct26/26 each, preserving0.7.0 closure2/2. No artifact regression against native. >=20% aggregate savings versus archived native controls on full seconds AND raw AND uncached. Fully audited counters required. Incomplete study cannot pass. No exact subscription-quota or population claim.',
              'stopping':'Stop on first candidate not fully correct and normally closed, fatal or partial meter, or observed3M total NEW raw tokens across stages001+002 at whole-trial boundaries. Never rerun failures. Keep planned2 fresh denominator. Historical controls excluded from new research costs.'})
    write(out/'protocol.json',m);write(out/'preregistered-protocol.json',m)
    print('REGISTERED',out,flush=True)


def run(out):
    m=json.loads((out/'protocol.json').read_text());assert m==json.loads((out/'preregistered-protocol.json').read_text())
    for case in m['cases']:
        rows=[json.loads(p.read_text())for p in(out/'trials').glob('*/record.json')]
        candidates=[r for r in rows if r['mode']=='goalpilot']
        if any(not r['success']or r['fatal']or not r['usage']['usage_complete']for r in candidates):
            write(out/'stopped.json',{'reason':'Preregistered candidate closure/correctness/meter futility','planned_fresh':2,'completed_fresh':len(candidates)});break
        if m['previous_stage_new_raw_tokens']+sum(r['usage']['total_tokens']for r in candidates)>=3000000:
            write(out/'stopped.json',{'reason':'Observed3M new raw cap across stages','planned_fresh':2,'completed_fresh':len(candidates)});break
        ident=case+'-goalpilot'
        if any(r['id']==ident for r in rows):continue
        assert hashes(out/'source_snapshot')==m['source_fingerprint']
        subprocess.run([sys.executable,str(out/'source_snapshot/tools/onepass_worker.py'),'worker',str(out),ident],check=True,cwd=out/'source_snapshot')
    subprocess.run([sys.executable,str(out/'source_snapshot/tools/onepass_worker.py'),'report',str(out)],check=True,cwd=out/'source_snapshot')


if __name__=='__main__':
    {'create':create,'run':run}[sys.argv[1]](Path(sys.argv[2]).resolve())
