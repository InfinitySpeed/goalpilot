"""Audit the 1.9 promotion, including its 1.8/native controls and all research cost."""
import argparse,hashlib,json,math,subprocess,tempfile,zipfile
from pathlib import Path,PurePosixPath
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_portability_extension import summarize
ROOT=Path(__file__).resolve().parents[1]
def sha(raw):return hashlib.sha256(raw).hexdigest()
def analyze(report,evidence=None,check_source=True):
 data=json.loads(Path(report).read_text());s=summarize(data['rows'])
 if s!=data['summary']:raise ValueError('Outcome summary differs')
 if check_source:
  for name,digest in data['source_files'].items():
   if sha((ROOT/name).read_bytes())!=digest:raise ValueError('Current promoted source differs: '+name)
 expected={'install.py','integrations/native/native.py','integrations/native/SKILL.md','integrations/native/routed-SKILL.md'}
 if set(data['source_files'])!=expected or set(data['measured_source_files'])!=expected:raise ValueError('Complete source identity required')
 for name in expected-{'install.py'}:
  if data['source_files'][name]!=data['measured_source_files'][name]:raise ValueError('Runtime changed after measurement')
 local=data['local_proof'];parity=data['install_parity']
 if local['candidate']['passed_methods']!=8 or local['control']['passed_methods']!=1 or local['candidate']['captured_files']!=local['control']['captured_files']or local['context_reduction_pct']!=100*(1-local['candidate']['context_bytes']/local['control']['context_bytes']):raise ValueError('Local counterfactuals differ')
 if set(parity)!=set(('codex','claude-code','antigravity','hermes','generic'))or any(len(p['measured'])!=55 or p['measured']!=p['deployed']for p in parity.values()):raise ValueError('Installed payload differs from measured candidate')
 n=s['totals']['current'];gates={'business_and_closure':n['business_passed']==n['certified']==4,'goals_preserved':s['gates']['goals_preserved'],'within_3pct_of_18':all(n[k]<=1.03*s['totals']['previous'][k]for k in('raw_tokens','uncached_tokens','seconds')),'positive_tokens_vs_native':all(n[k]<s['totals']['native'][k]for k in('raw_tokens','uncached_tokens')),'time_vs_native_within_3pct':n['seconds']<=1.03*s['totals']['native']['seconds'],'expanded_capabilities':local['context_reduction_pct']>=70}
 if gates!=data['promotion_gates']:raise ValueError('Promotion gates differ')
 if evidence:
  if sha(Path(evidence).read_bytes())!=data['evidence_sha256']:raise ValueError('Archive differs')
  with zipfile.ZipFile(evidence)as z:
   files=data['evidence_files']
   if set(z.namelist())!=set(files)or len(z.namelist())!=len(files):raise ValueError('Evidence inventory differs')
   for name,digest in files.items():
    if sha(z.read(name))!=digest:raise ValueError('Evidence digest differs: '+name)
   for name,digest in data['measured_source_files'].items():
    if sha(z.read('inputs/measured/'+name))!=digest:raise ValueError('Measured source differs')
   if json.loads(z.read('protocol.json'))!=data['protocol']:raise ValueError('Protocol differs')
   for row in data['rows']:
    prefix='selected/'+row['case']+'-'+row['arm']+'/'
    outcome=json.loads(z.read(prefix+'original-outcome.json'));normalized={**outcome,'arm':row['arm']}
    if normalized!=row:raise ValueError('Outcome relabelled beyond declared arm mapping')
    updates=[json.loads(x)for x in z.read(prefix+'usage.jsonl').splitlines()];v=updates[-1]['params']['tokenUsage']['total']
    if [row['usage'][k]for k in('input_tokens','output_tokens','cached_input_tokens')]!=[v[k]for k in('inputTokens','outputTokens','cachedInputTokens')]:raise ValueError('Provider counter differs')
   ledger=json.loads(z.read('research-ledger.json'))
   if ledger!=data['research_usage']:raise ValueError('Research ledger differs')
 return {'summary':s,'promotion_gates':gates,'promotable':all(gates.values())}
def replay(data,path):
 results=[]
 with zipfile.ZipFile(path)as z:
  for row in data['rows']:
   prefix='selected/'+row['case']+'-'+row['arm']+'/repo/'
   with tempfile.TemporaryDirectory()as tmp:
    work=Path(tmp)
    for name in data['evidence_files']:
     if not name.startswith(prefix):continue
     rel=PurePosixPath(name[len(prefix):])
     if rel.is_absolute()or'..'in rel.parts or'\\'in str(rel):raise ValueError('Unsafe evidence path')
     p=work/str(rel);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
    judge=json.loads(z.read('judges/'+row['case']+'.json'));(work/judge['filename']).write_text(judge['source'])
    r=subprocess.run(judge['argv'],cwd=work,capture_output=True,text=True,timeout=90);correct=r.returncode==0
    results.append({'case':row['case'],'arm':row['arm'],'correct':correct,'matches':correct==row['correct']})
 return results
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('report');p.add_argument('--evidence');p.add_argument('--replay',action='store_true');p.add_argument('--require-promotion',action='store_true');a=p.parse_args()
 result=analyze(a.report,a.evidence)
 if a.replay:
  if not a.evidence:p.error('--replay requires --evidence')
  result['replay']=replay(json.loads(Path(a.report).read_text()),a.evidence)
 print(json.dumps(result,indent=2))
 raise SystemExit(int(a.require_promotion and not result['promotable']or a.replay and not all(r['matches']for r in result['replay'])))
