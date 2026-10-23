"""Recompute the generalized skill's whole-caller comparison without model calls."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]

def sha(raw):return hashlib.sha256(raw).hexdigest()

def analyze(path,evidence=None,*,check_source=True):
    report=json.loads(Path(path).read_text());rows=report['trials'];cases=report['cases']
    expected={(case,arm)for case in cases for arm in ('native','old','new')}
    if len(cases)!=8 or len(rows)!=24 or {(r['case'],r['arm'])for r in rows}!=expected:
        raise ValueError('All24 registered outcomes required, without replacement')
    allowed={'install.py','integrations/native/native.py','integrations/native/SKILL.md','integrations/native/routed-SKILL.md'}
    if set(report['source_files'])!=allowed:raise ValueError('Complete measured source identity required')
    if check_source:
        for name,digest in report['source_files'].items():
            if sha((ROOT/name).read_bytes())!=digest:raise ValueError('Measured source differs: '+name)
    archive=None
    if evidence:
        raw=Path(evidence).read_bytes()
        if sha(raw)!=report['evidence']['sha256']:raise ValueError('Evidence archive differs')
        archive=tarfile.open(evidence,'r:xz')
    if archive:
        for campaign in ('primary','final','retired'):
            entry=archive.getmember(campaign+'/protocol.json')
            protocol=json.load(archive.extractfile(entry))
            for name,expected_hash in protocol['source_hashes'].items():
                item=archive.getmember(campaign+'/'+name)
                if not item.isfile()or item.size>8_000_000 or sha(archive.extractfile(item).read())!=expected_hash:raise ValueError('Frozen source changed')
    scores={}
    try:
        for arm in ('native','old','new'):
            selected=[r for r in rows if r['arm']==arm]
            score={'business_correct':0,'certified':0,'goals_preserved':0,'raw_tokens':0,'uncached_plus_output':0,'seconds':0.0}
            for r in selected:
                i,o,c=r['tokens']
                if any(type(v)is not int or v<0 for v in (i,o,c))or c>i or i==0 or o==0:raise ValueError('Invalid provider meter')
                if sha(json.dumps(r['tokens'],separators=(',',':')).encode())!=r['meter_sha256']:raise ValueError('Provider meter changed')
                if type(r['seconds'])not in(int,float)or not math.isfinite(r['seconds'])or r['seconds']<=0:raise ValueError('Invalid caller elapsed time')
                if archive:
                    def member(name):
                        f=archive.getmember(name)
                        if not f.isfile()or f.size>8_000_000:raise ValueError('Unsafe evidence member')
                        return archive.extractfile(f).read()
                    raw=member(r['trial']+'/result.json')
                    if sha(raw)!=r['receipt_sha256']:raise ValueError('Caller outcome differs')
                    outcome=json.loads(raw)
                    if [outcome['usage'][k]for k in ('input_tokens','output_tokens','cached_input_tokens')]!=r['tokens']:raise ValueError('Outcome meter differs')
                    updates=[json.loads(line)for line in member(r['trial']+'/provider-updates.jsonl').splitlines()]
                    final=updates[-1]['params']['tokenUsage']['total']
                    if [final[k]for k in ('inputTokens','outputTokens','cachedInputTokens')]!=r['tokens']:raise ValueError('Provider notifications differ')
                    if any(outcome[k]!=r[k]for k in ('correct','certified','goal_preserved','seconds')):raise ValueError('Outcome relabelled')
                    if not outcome['usage']['usage_complete']:raise ValueError('Incomplete caller meter')
                score['business_correct']+=r['correct']is True
                score['certified']+=r['certified']is True
                score['goals_preserved']+=r['goal_preserved']is True
                score['raw_tokens']+=i+o;score['uncached_plus_output']+=i-c+o;score['seconds']+=r['seconds']
            scores[arm]=score
    finally:
        if archive:archive.close()
    n=scores['new'];b=scores['native']
    gains={key:100*(1-n[key]/b[key])for key in ('raw_tokens','uncached_plus_output','seconds')}
    service=[r for r in rows if r['case'].startswith('service-')and r['arm']=='new']
    promotable=(n['business_correct']==n['certified']==n['goals_preserved']==8 and
                n['business_correct']>=b['business_correct'] and gains['raw_tokens']>=10 and
                gains['uncached_plus_output']>0 and gains['seconds']>=-3 and
                len(service)==2 and all(r['certified']and r['correct']for r in service))
    return {'scores':scores,'savings_vs_native_percent':gains,'promotable':promotable,'full_evidence_checked':bool(evidence)}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('report');p.add_argument('--evidence');p.add_argument('--require-promotion',action='store_true')
    a=p.parse_args();result=analyze(a.report,a.evidence);print(json.dumps(result,indent=2))
    if a.require_promotion and not result['promotable']:raise SystemExit(1)
