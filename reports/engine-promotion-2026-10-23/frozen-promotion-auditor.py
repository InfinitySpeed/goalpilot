#!/usr/bin/env python3
"""Derive promotion gates from frozen per-goal evidence, never a hand-written score."""
from pathlib import Path
import argparse,hashlib,json,math,zipfile


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def hashes(root):return {str(p.relative_to(root)):sha(p)for p in sorted(root.rglob('*'))if p.is_file()and '__pycache__'not in p.parts and p.suffix!='.pyc'}
def audit_meter(trial,state):
    previous={};sums={'input_tokens':0,'output_tokens':0,'cached_input_tokens':0}
    for index,call in enumerate(state['calls'],1):
        result=call['result'];assert result['usage_complete'] and result['returncode']==0
        events=trial/'engine/calls'/str(index)/'events.jsonl';packets=[json.loads(line)['packet']for line in events.read_text().splitlines()]
        packets=[p for p in packets if p.get('method')=='thread/tokenUsage/updated']
        assert packets,'Missing provider meter updates'
        last=packets[-1]['params'];thread=last['threadId'];total=last['tokenUsage']['total'];before=previous.get(thread,dict(inputTokens=0,outputTokens=0,cachedInputTokens=0))
        mapping={'input_tokens':'inputTokens','output_tokens':'outputTokens','cached_input_tokens':'cachedInputTokens'}
        for dest,source in mapping.items():
            amount=total[source]-before[source];assert amount==result['usage'][dest],(trial,dest,amount,result['usage'][dest]);sums[dest]+=amount
        previous[thread]=total
    sums['total_tokens']=sums['input_tokens']+sums['output_tokens'];sums['uncached_tokens']=sums['total_tokens']-sums['cached_input_tokens']
    return sums


def analyze(cohort):
    cohort=Path(cohort);p=json.loads((cohort/'protocol.json').read_text());rows=[]
    assert len(set(p['cases']))==len(p['cases'])
    assert hashes(cohort/'source')==p['source_hashes'];assert hashes(cohort/'harness')==p['harness_hashes']
    for case in p['cases']:
        trial=cohort/'trials'/case
        if not (trial/'result.json').exists():continue
        row=json.loads((trial/'result.json').read_text());assert row['case']==case
        state=json.loads((trial/'engine/state.json').read_text())
        counter=audit_meter(trial,state)
        for key,value in counter.items():assert value==row['usage'][key]
        assert hashes(trial/'delivered')==row['artifact_hashes']
        for receipt in json.loads((trial/'engine/helpers.json').read_text()):
            assert sha(trial/'delivered'/Path(receipt['path']).name)==receipt['sha256']
        assert row['normal_closure']==(state['status']in ('completed','scope_passed'))
        reviewed=row['reviewed_judge'];assert reviewed['correct']==(reviewed['returncode']==0 and len(reviewed['groups_passed'])==10)
        assert row['success']==(row['normal_closure']and reviewed['correct'])
        assert row['sources_unchanged'] and row['usage']['usage_complete']
        assert row['model']['model']=='gpt-6.1-sol' and row['model']['reasoningEffort']=='low'
        rows.append(row)
    metric={'executed':len(rows),'correct':sum(r['success']for r in rows),'strict_correct':sum(r['normal_closure']and r['strict_correct']for r in rows),'seconds':sum(r['seconds']for r in rows),'raw':sum(r['usage']['total_tokens']for r in rows),'uncached_plus_output':sum(r['usage']['uncached_tokens']for r in rows),'uncached_input':sum(r['usage']['input_tokens']-r['usage']['cached_input_tokens']for r in rows),'output':sum(r['usage']['output_tokens']for r in rows),'calls':sum(r['calls']for r in rows),'meter_complete':bool(rows)and all(r['usage']['usage_complete']for r in rows)}
    baseline_path=Path(p['controls_path']);assert sha(baseline_path)==p['controls_sha256']
    baseline=json.loads(baseline_path.read_text())
    included={row['case']for row in rows}
    matched={}
    for arm in ['new','native']:
        base_rows=[r for r in baseline['rows']if r['arm']==arm and r['case']in included]
        assert len(base_rows)==len(rows)
        base={key:sum(r['seconds']if key=='seconds'else r['usage']['output_tokens'if key=='output'else key]for r in base_rows)for key in ['seconds','raw','uncached_plus_output','uncached_input','output']}
        matched[arm]={key:100*(1-metric[key]/base[key])if base[key]else 0 for key in base}
    gates={'all_20':len(rows)==20 and set(p['cases'])==set(p['full_case_list']),'all_correct':metric['correct']==20,'all_meters_complete':metric['meter_complete'],'time_saving_vs_native':matched['native']['seconds']>=25,'raw_saving_vs_native':matched['native']['raw']>=45,'uncached_saving_vs_native':matched['native']['uncached_plus_output']>=45,'input_saving_vs_native':matched['native']['uncached_input']>=45,'output_saving_vs_native':matched['native']['output']>=45,'time_vs_current':matched['new']['seconds']>=-3,'raw_vs_current':matched['new']['raw']>=-3,'uncached_vs_current':matched['new']['uncached_plus_output']>=-3}
    gates['meaningful_raw_gain_vs_current']=matched['new']['raw']>=15
    gates['meaningful_uncached_gain_vs_current']=matched['new']['uncached_plus_output']>=15
    return {'cohort':p['cohort'],'phase':p['phase'],'metrics':metric,'saving_percent':matched,'gates':gates,'promotable':all(gates.values()),'source_hashes':p['source_hashes'],'protocol_sha256':sha(cohort/'protocol.json'),'report_scope':'Known public synthetic benchmark; historical controls; no arbitrary-request or exact subscription quota claim.'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('cohort',type=Path);ap.add_argument('--output',type=Path);ap.add_argument('--require-promotion',action='store_true');ap.add_argument('--artifact',type=Path);a=ap.parse_args()
    report=analyze(a.cohort)
    if a.artifact:
        with zipfile.ZipFile(a.artifact) as archive:
            manifest=json.loads(archive.read('GOALPILOT-FROZEN.json'))
            files={name:hashlib.sha256(archive.read(name)).hexdigest()for name in archive.namelist()if not name.endswith('/')and name!='GOALPILOT-FROZEN.json'}
        assert files==report['source_hashes']
        assert manifest['protocol_sha256']==report['protocol_sha256']
        assert manifest['source_hashes']==report['source_hashes']
        assert manifest['status']=='promoted'and report['promotable']
        report['artifact_sha256']=sha(a.artifact)
    if a.output:a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 2 if a.require_promotion and not report['promotable']else 0
if __name__=='__main__':raise SystemExit(main())
