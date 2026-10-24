"""Recompute the immutable historical 1.12 fast-path evidence without comparing it to today's default."""
import hashlib, json, math, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/skill-112-adaptive-fast-path-2026-10-24.json'
ARCHIVE=ROOT/'reports/skill-112-evidence.zip'
def sha_bytes(data): return hashlib.sha256(data).hexdigest()
def sha(path): return sha_bytes(path.read_bytes())
def audit():
 d=json.loads(REPORT.read_text())
 if d.get('version')!='1.12.0' or d.get('status')!='promotable': raise ValueError('historical 1.12 evidence identity mismatch')
 with zipfile.ZipFile(ARCHIVE) as zf:
  names=set(zf.namelist())
  if 'reports/skill-112-adaptive-fast-path-2026-10-24.json' not in names or sha_bytes(zf.read('reports/skill-112-adaptive-fast-path-2026-10-24.json'))!=sha(REPORT): raise ValueError('archived report mismatch')
  source='integrations/native/routed-SKILL.md'
  if source not in names or sha_bytes(zf.read(source))!=d['candidate_source_sha256']: raise ValueError('archived 1.12 source mismatch')
 for family,arms in d['per_family'].items():
  for arm,row in arms.items():
   if len(row['trials'])!=2 or row['correct']!=2: raise ValueError(f'incomplete or incorrect paired runs: {family}/{arm}')
   for k in ('raw_tokens','cached_input_tokens','uncached_tokens','seconds'):
    m=sum(t[k] for t in row['trials'])/2
    if not math.isclose(m,row['means'][k],abs_tol=1e-8): raise ValueError(f'mean mismatch: {family}/{arm}/{k}')
   if any(t['independent_judge_passed'] is not True for t in row['trials']): raise ValueError('independent judge failure')
   if arm=='candidate' and any(t['project_tests_passed'] is not True for t in row['trials']): raise ValueError('project suite failure')
 for arm in ('candidate','current','native'):
  recomputed={k:sum(d['per_family'][f][arm]['means'][k] for f in d['per_family'])/len(d['per_family']) for k in ('raw_tokens','cached_input_tokens','uncached_tokens','seconds')}
  for k,v in recomputed.items():
   if not math.isclose(v,d['summary'][arm]['equal_weight_family_means'][k],abs_tol=1e-8): raise ValueError(f'aggregate mismatch: {arm}/{k}')
 for control in ('current','native'):
  delta=d['summary']['candidate']['change_vs_'+control]
  if delta['uncached_tokens']>=0 or delta['seconds']>3: raise ValueError(f'historical 1.12 gate failed vs {control}')
 guard=d['complex_fallback_guard']
 if guard['correct']!=2 or guard['certified']!=2: raise ValueError('complex full-workflow fallback guard failed')
 if d['promotion_gate']['raw_tokens_used_as_quota_evidence'] is not False: raise ValueError('raw-token quota claim is forbidden')
 if len(d['all_recorded_trials_in_experiment'])<len(d['per_family'])*6: raise ValueError('run-level outcomes missing')
 return {'historical_evidence_valid':True,'version':'1.12.0','candidate_source_sha256':d['candidate_source_sha256'],'archive_sha256':sha(ARCHIVE)}
if __name__=='__main__': print(json.dumps(audit(),indent=2))
