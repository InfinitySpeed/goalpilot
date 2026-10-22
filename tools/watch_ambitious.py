"""Read-only observer: retain pre-review code, never alter a worker or supply feedback."""
import hashlib,json,shutil,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from goalpilot.engine import atomic_json
IGNORE={'.git','__pycache__','.venv','node_modules','.pytest_cache'}


def watch(output):
    output=Path(output).resolve();m=json.loads((output/'protocol.json').read_text());base=output/'exploratory-pre-review';base.mkdir(exist_ok=True)
    atomic_json(base/'diagnostic-protocol.json',{'registered_at_utc_epoch':time.time(),'status':'Additional exploratory diagnostic registered after the primary campaign began, before any diagnostic judgments. No change to primary protocol, trials or scoring.','method':'Observe persisted audit call reservations and copy the quiescent repository at the beginning of its read-only completion review. Check byte stability. Only evaluate copies after the entire primary campaign; no judge feedback ever supplied to workers. Snapshots are not independent trials or new model usage.','limits':'Best-effort file copy, not an atomic filesystem snapshot. Changed/omitted files or absolute original-repository dependencies prevent strong before/after attribution.'})
    stop=time.monotonic()+4*3600
    while time.monotonic()<stop:
        done=[]
        for item in m['order']:
            trial=output/'trials'/item['id'];record=trial/'record.json'
            if record.exists():done.append(json.loads(record.read_text()))
            if item['mode']!='goalpilot'or(base/item['id']).exists():continue
            flow=trial/'run/finish-run.json'
            if not flow.exists():continue
            try:f=json.loads(flow.read_text());pending=f.get('pending');calls=f['calls']
            except(json.JSONDecodeError,OSError):continue
            if not pending or calls[pending['index']]['strategy']!='audit':continue
            repo=output/'repos'/item['id'];dest=base/item['id'];files=[];omitted=[];used=0;stamps={}
            for p in sorted(repo.rglob('*')):
                rel=p.relative_to(repo)
                if p.is_symlink()or any(part in IGNORE for part in rel.parts)or not p.is_file():continue
                if p.name.startswith('.env')or p.name.lower()in('auth.json','credentials.json'):continue
                size=p.stat().st_size
                if size+used>10000000 or len(files)>=2000:omitted.append(str(rel));continue
                raw=p.read_bytes();stamps[str(rel)]=hashlib.sha256(raw).hexdigest();q=dest/'repo'/rel;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(raw);files.append(str(rel));used+=len(raw)
            stable=all((repo/path).is_file()and hashlib.sha256((repo/path).read_bytes()).hexdigest()==sha for path,sha in stamps.items())
            absolute=[name for name in files if name.endswith('.py')and str(repo).encode()in(dest/'repo'/name).read_bytes()]
            atomic_json(dest/'snapshot.json',{'captured_at_epoch':time.time(),'call':pending['index']+1,'strategy':'audit','files_sha256':stamps,'omitted':omitted,'copied_files_stable':stable,'python_files_with_original_repo_literal':absolute,'all_call_results_before_snapshot':calls[:pending['index']]})
            print(json.dumps({'snapshot':item['id'],'files':len(files),'bytes':used,'stable':stable,'omitted':omitted}),flush=True)
        if len(done)==len(m['order'])or any(r['fatal']or r['infrastructure_interruption']for r in done)or sum(r['usage']['total_tokens']for r in done)>=m['campaign_observed_token_cap']:break
        time.sleep(1)


if __name__=='__main__':watch(sys.argv[1])
