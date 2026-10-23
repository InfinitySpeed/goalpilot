"""Source-bound audit of the 1.10 four-goal raw-token promotion."""
import argparse, hashlib, json, zipfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_portability_extension import summarize
ROOT=Path(__file__).resolve().parents[1]
def sha(raw): return hashlib.sha256(raw).hexdigest()
def audit(report,evidence,check_source=True):
    report=Path(report); evidence=Path(evidence); d=json.loads(report.read_text())
    if d['skill_version']!='1.10.0' or d['native_adapter_version']!='0.3.0': raise ValueError('Release identity mismatch')
    summary=summarize(d['rows'])
    if summary!=d['summary']: raise ValueError('Recomputed summary differs')
    if check_source:
        for name,digest in d['source_files'].items():
            if sha((ROOT/name).read_bytes())!=digest: raise ValueError('Promoted source differs: '+name)
    if set(d['source_files'])!={'install.py','integrations/native/native.py','integrations/native/routed-SKILL.md','integrations/native/SKILL.md'}: raise ValueError('Incomplete source identity')
    if d['measured_source_files']['integrations/native/native.py']!=d['source_files']['integrations/native/native.py'] or d['measured_source_files']['integrations/native/routed-SKILL.md']!=d['source_files']['integrations/native/routed-SKILL.md'] or d['measured_source_files']['integrations/native/SKILL.md']!=d['source_files']['integrations/native/SKILL.md']: raise ValueError('Measured runtime source changed')
    current=summary['totals']['current']; previous=summary['totals']['previous']; native=summary['totals']['native']
    gates={
      'four_correct_closed_preserved':current['business_passed']==current['certified']==4 and all(r['goal_preserved'] is True for r in d['rows'] if r['arm']=='current'),
      'raw_tokens_190k_to_210k':190000<=current['raw_tokens']<=210000,
      'raw_tokens_below_19_and_native':current['raw_tokens']<previous['raw_tokens'] and current['raw_tokens']<native['raw_tokens'],
      'aggregate_time_no_regression':current['seconds']<=previous['seconds'] and current['seconds']<=native['seconds'],
      'installed_runtime_matches_measured':d['runtime_parity']['all_behavior_files_match'],
    }
    if gates!=d['promotion_gates']: raise ValueError('Promotion gates differ')
    if sha(evidence.read_bytes())!=d['evidence']['sha256']: raise ValueError('Evidence archive digest differs')
    with zipfile.ZipFile(evidence) as z:
        if set(z.namelist())!=set(d['evidence']['files']) or len(z.namelist())!=len(set(z.namelist())): raise ValueError('Evidence inventory differs')
        for n,h in d['evidence']['files'].items():
            if sha(z.read(n))!=h: raise ValueError('Evidence digest differs: '+n)
        if sha(z.read('controls/skill-190-report.json'))!=d['controls']['report_sha256']: raise ValueError('Control report differs')
        if sha(z.read('controls/skill-190-evidence.zip'))!=d['controls']['evidence_sha256']: raise ValueError('Control evidence differs')
        for r in d['rows']:
            if r['arm']!='current':
                old_arm='current' if r['arm']=='previous' else r['arm']
                old=json.loads(z.read('controls/skill-190-report.json'))
                oldrow=next(x for x in old['rows'] if x['case']==r['case'] and x['arm']==old_arm)
                if {**oldrow,'arm':r['arm']}!=r: raise ValueError('Control row changed')
                continue
            base=f"selected/{r['case']}-current/"
            result=json.loads(z.read(base+'result.json'))
            if result!=r: raise ValueError('Candidate result changed')
            updates=[json.loads(x) for x in z.read(base+'caller/events.jsonl').decode().splitlines() if x.strip()]
            meters=[]
            for x in updates:
                packet=x.get('packet',x)
                if packet.get('method')=='thread/tokenUsage/updated': meters.append(packet['params']['tokenUsage']['total'])
            if not meters: raise ValueError('Provider usage updates absent')
            u=meters[-1]
            for public,provider in [('input_tokens','inputTokens'),('output_tokens','outputTokens'),('cached_input_tokens','cachedInputTokens')]:
                if r['usage'][public]!=u[provider]: raise ValueError('Provider meter mismatch')
            if not r['correct'] or not r['certified'] or not r['goal_preserved']: raise ValueError('Candidate did not correctly close all goals')
        protocol=json.loads(z.read('study/protocol.json'))
        if protocol!=d['protocol']: raise ValueError('Frozen protocol differs')
    return {'summary':summary,'promotion_gates':gates,'promotable':all(gates.values()),'uncached_change_vs_19_pct':summary['comparisons']['previous']['uncached_tokens_saving_pct'],'cache_controlled':False}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('report');p.add_argument('--evidence',required=True);p.add_argument('--require-promotion',action='store_true');a=p.parse_args();r=audit(a.report,a.evidence);print(json.dumps(r,indent=2));raise SystemExit(int(a.require_promotion and not r['promotable']))
