import copy,csv,hashlib,io,json,os,subprocess,sys,tempfile
from pathlib import Path
repo=Path(sys.argv[1]);sys.path.insert(0,str(repo))
import app as m
passed=[]
def check(group):passed.append(group);print('PASS',group,flush=True)
with tempfile.TemporaryDirectory(prefix='gp-judge-') as tmp:
 db=Path(tmp)/'data.json'
 def c(operation,**data):
  original=copy.deepcopy(data)
  value=m.Service(db).call(operation,data)
  assert data==original,'Application modified caller input'
  json.dumps(value,allow_nan=False)
  return value
 def reject(operation,**data):
  before=db.read_bytes() if db.exists() else None
  original=copy.deepcopy(data)
  try:m.Service(db).call(operation,data)
  except ValueError:pass
  else:raise AssertionError('Invalid request accepted: '+operation)
  assert data==original,'Rejected request changed caller input'
  assert (db.read_bytes() if db.exists() else None)==before,'Rejected request changed persisted data'
 
 c('queue.create',id='q',max_attempts=2,retry_delay=5)
 a=c('message.publish',queue='q',id='a',payload={'café':[1]},key='a',priority=1)
 c('message.publish',queue='q',id='b',payload=2,key='b',priority=3)
 assert c('message.publish',queue='q',id='a',payload={'café':[1]},key='a',priority=1)==a
 rows=c('claim',queue='q',worker='w',now=0,lease=10,limit=1);assert rows[0]['id']=='b' and rows[0]['attempts']==1
 old=rows[0]['receipt'];c('nack',queue='q',id='b',receipt=old,now=1)
 assert [r['id']for r in c('claim',queue='q',worker='w',now=2,lease=10,limit=2)]==['a']
 check('priority_idempotency_delayed_retry')
 rows=c('claim',queue='q',worker='x',now=6,lease=2,limit=2);assert [r['id']for r in rows]==['b'] and rows[0]['attempts']==2
 assert rows[0]['receipt']!=old
 before=db.read_bytes();reject('ack',queue='q',id='b',receipt=old,now=7);assert db.read_bytes()==before
 stats=c('queue.stats',queue='q',now=8);assert stats['dead']==1 and stats['leased']==1
 c('redrive',queue='q',id='b',now=8);r=c('claim',queue='q',worker='x',now=8,lease=3,limit=1)[0]
 assert r['id']=='b' and r['attempts']==1;c('ack',queue='q',id='b',receipt=r['receipt'],now=9)
 check('lease_expiry_dead_letter_redrive')
 assert c('message.get',queue='q',id='b')['status']=='done'
 c('message.publish',queue='q',id='c',payload=None,key='c');c('message.cancel',queue='q',id='c')
 assert c('queue.stats',queue='q',now=20)=={'pending':1,'leased':0,'done':1,'dead':0,'cancelled':1}
 check('completion_cancellation_restart')
 before=db.read_bytes();reject('publish.import',messages=[{'queue':'q','id':'x','payload':0,'key':'batch'},{'queue':'missing','id':'y','payload':0,'key':'bad'}]);assert db.read_bytes()==before
 reject('claim',queue='q',worker='x',now=21,lease=True,limit=1)
 check('batch_and_types')

 business_db=db
 for attempt in range(3):
  db=Path(tmp)/('race-'+str(attempt)+'.json')
  c('queue.create',id='q',max_attempts=2,retry_delay=0);c('message.publish',queue='q',id='m',payload=1,key='m')
  packets=[('claim', {'queue': 'q', 'worker': 'a', 'now': 0, 'lease': 10, 'limit': 1}), ('claim', {'queue': 'q', 'worker': 'b', 'now': 0, 'lease': 10, 'limit': 1})]
  workers=[]
  try:
   for operation,data in packets:
    code="import json,sys;from app import Service;s=Service(sys.argv[1]);print('READY',flush=True);sys.stdin.readline();op,data=json.loads(sys.argv[2]);\ntry:r=s.call(op,data);print(json.dumps({'ok':True,'result':r}),flush=True)\nexcept ValueError as e:print(json.dumps({'ok':False,'error':str(e)}),flush=True)"
    p=subprocess.Popen([sys.executable,'-c',code,str(db),json.dumps([operation,data])],cwd=repo,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    workers.append(p)
   # Bounded READY wait via selectors, without trusting application output.
   import selectors,time,signal
   with selectors.DefaultSelector() as ready:
    for p in workers:ready.register(p.stdout,selectors.EVENT_READ)
    until=time.monotonic()+10
    pending=set(workers)
    while pending:
     events=ready.select(max(0,until-time.monotonic()))
     assert events,'Concurrent worker initialization timeout'
     for key,_ in events:
      p=next(p for p in pending if p.stdout is key.fileobj)
      assert p.stdout.readline().strip()=='READY','Concurrent worker failed initialization'
      pending.remove(p);ready.unregister(p.stdout)
   for p in workers:p.stdin.write('go\n');p.stdin.flush()
   results=[]
   for p in workers:
    out,err=p.communicate(timeout=10);assert p.returncode==0,err
    results.append(json.loads(out))
   mode='one_acquired'
   if mode=='one_success':assert sum(x['ok']for x in results)==1,results
   elif mode=='one_enrolled':assert all(x['ok']for x in results) and sorted(x['result']['status']for x in results)==['enrolled','waiting'],results
   elif mode=='one_nonnull':assert all(x['ok']for x in results) and sum(x['result']is not None for x in results)==1,results
   elif mode=='one_acquired':assert all(x['ok']for x in results) and sum(len(x['result'])for x in results)==1,results
   elif mode=='one_invoice':assert all(x['ok']for x in results) and sum(len(x['result']['invoices'])for x in results)==1,results
  finally:
   for p in workers:
    if p.poll() is None:
     try:__import__('os').killpg(p.pid,__import__('signal').SIGKILL)
     except ProcessLookupError:pass
    p.wait(timeout=2)
 db=business_db
 check('three_real_cross_process_conflict_races')
 snapshot=c('backup');original=copy.deepcopy(snapshot)
 snapshot['__judge_detachment_probe__']=True
 assert c('backup')==original,'Backup aliases live state'
 check('detached_snapshots_and_restart')
 reject('restore',state=[]);reject('restore',state={'__invalid_service_state__':True})
 c('restore',state=original);assert c('backup')==original
 check('restore_rejects_invalid_without_data_loss')
 argv=[sys.executable,str(repo/'app.py'),'--file',str(db)]
 packets=[{'operation':'backup','data':{}},{'operation':'__unknown_operation__','data':{}},[],{'operation':'backup','data':{}}]
 raw='bad-json\n'+''.join(json.dumps(x,ensure_ascii=False)+'\n'for x in packets)
 result=subprocess.run([*argv,'jsonl'],input=raw,text=True,capture_output=True,timeout=15,cwd=repo)
 assert result.returncode==0,result.stderr
 rows=[json.loads(line)for line in result.stdout.splitlines()]
 assert len(rows)==5 and [r['ok']for r in rows]==[False,True,False,False,True],rows
 assert rows[1]['result']==rows[4]['result']==original
 assert all(rows[i].get('error')for i in (0,2,3))
 check('real_jsonl_errors_and_recovery')
 from host_helpers import json_http
 with json_http([*argv,'serve','--port','0'],cwd=repo) as request:
  assert request('GET','/health')=={'ok':True}
  assert request('POST','/api',{'operation':'backup','data':{}})=={'ok':True,'result':original}
  assert request('POST','/api',[],status=400).get('ok') is False
  assert request('POST','/api',{'operation':'__unknown_operation__'},status=400).get('ok') is False
  assert request('GET','/not-a-path',status=404).get('ok') is False
 check('real_http_domain_errors_health')
 assert c('backup')==original
 assert (repo/'USER_NOTES.txt').read_bytes()=='Original customer data: café 東京\nPreserve this document.\n'.encode()
 assert m.banner()=='Local Ops — café'
 check('original_behavior_and_customer_data')
