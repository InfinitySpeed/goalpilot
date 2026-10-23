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
 
 c('customer.put',id='c',name='Zoé');r=c('invoice.create',id='i',customer='c',lines=[{'description':'A','quantity':3,'unit_cents':15}],tax_bps=1000)
 assert (r['subtotal'],r['tax'],r['total'],r['balance'])==(45,5,50,50)
 reject('invoice.pay',id='i',amount=1,key='early')
 c('invoice.issue',id='i',expected_revision=1);r=c('invoice.pay',id='i',amount=20,key='p1')
 assert r['status']=='partial' and r['paid']==20 and r['balance']==30
 assert c('invoice.pay',id='i',amount=20,key='p1')==r
 check('rounding_issue_payment')
 before=db.read_bytes();reject('invoice.pay',id='i',amount=21,key='p1');reject('invoice.credit',id='i',amount=31,key='c1');assert db.read_bytes()==before
 r=c('invoice.credit',id='i',amount=10,key='c1');assert r['balance']==20
 c('invoice.pay',id='i',amount=20,key='p2');assert c('invoice.get',id='i')['status']=='paid'
 assert c('statement',customer='c')=={'invoiced':50,'paid':40,'credited':10,'due':0}
 check('credit_idempotency_statement')
 c('invoice.create',id='v',customer='c',lines=[{'description':'V','quantity':1,'unit_cents':100}],tax_bps=0)
 c('invoice.void',id='v',expected_revision=1);reject('invoice.issue',id='v',expected_revision=2)
 assert c('statement',customer='c')['invoiced']==50
 check('void_lifecycle')
 c('invoice.create',id='b',customer='c',lines=[{'description':'B','quantity':1,'unit_cents':100}],tax_bps=0);c('invoice.issue',id='b',expected_revision=1)
 before=db.read_bytes();reject('payment.import',payments=[{'id':'b','amount':50,'key':'batch1'},{'id':'b','amount':60,'key':'batch2'}]);assert db.read_bytes()==before
 reject('invoice.pay',id='b',amount=True,key='bool');assert c('invoice.get',id='b')['paid']==0
 check('batch_and_types')

 business_db=db
 for attempt in range(3):
  db=Path(tmp)/('race-'+str(attempt)+'.json')
  c('customer.put',id='c',name='C');c('invoice.create',id='i',customer='c',lines=[{'description':'A','quantity':1,'unit_cents':100}],tax_bps=0);c('invoice.issue',id='i',expected_revision=1)
  packets=[('invoice.pay', {'id': 'i', 'amount': 80, 'key': 'a'}), ('invoice.pay', {'id': 'i', 'amount': 80, 'key': 'b'})]
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
   mode='one_success'
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
