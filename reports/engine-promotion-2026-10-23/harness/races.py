"""Public-interface cross-process safety scenarios; independent of storage internals."""
RACES={
'rental':("c('asset.put',id='p',quantity=1,rate=1)", [('booking.create',{'id':x,'asset':'p','quantity':1,'start':0,'end':10,'key':x})for x in ['a','b']], 'one_success'),
'invoices':("c('customer.put',id='c',name='C');c('invoice.create',id='i',customer='c',lines=[{'description':'A','quantity':1,'unit_cents':100}],tax_bps=0);c('invoice.issue',id='i',expected_revision=1)", [('invoice.pay',{'id':'i','amount':80,'key':x})for x in ['a','b']], 'one_success'),
'learning':("c('student.put',id='a',name='A');c('student.put',id='b',name='B');c('course.put',id='c',prerequisites=[],capacity=1,price=1)", [('enroll',{'student':x,'course':'c','key':x})for x in ['a','b']], 'one_enrolled'),
 'tickets':("c('event.create',id='e',seats=['A'],price=1)", [('hold.create',{'id':x,'event':'e','seats':['A'],'now':0,'ttl':10})for x in ['a','b']], 'one_success'),
'procurement':("c('department.put',id='d',budget=100);c('member.put',id='r',department='d',role='requester');c('member.put',id='a',department='d',role='approver');c('request.create',id='x',creator='r',amount=80,approvals=1);c('request.create',id='y',creator='r',amount=80,approvals=1)", [('request.approve',{'id':x,'actor':'a','expected_revision':1})for x in ['x','y']], 'one_success'),
'accounting':("c('account.create',id='a',name='A',kind='asset');c('account.create',id='b',name='B',kind='income');c('period.create',id='p',start=0,end=10)", [('journal.post',{'id':'e','date':1,'lines':[{'account':'a','debit':1,'credit':0},{'account':'b','debit':0,'credit':1}],'key':x})for x in ['x','y']], 'one_success'),
'clinic':("c('practitioner.put',id='dr',skills=['x']);c('patient.put',id='a',consent=True);c('patient.put',id='b',consent=True)", [('appointment.create',{'id':x,'patient':x,'practitioner':'dr','start':0,'end':10,'skill':'x','fee':1,'key':x})for x in ['a','b']], 'one_success'),
'incidents':("c('team.put',id='t',members=['a','b']);c('policy.put',id='p',response=1,resolve=2);c('incident.open',id='i',team='t',policy='p',now=0,title='I',key='i')", [('incident.assign',{'id':'i','owner':x,'expected_revision':1,'now':1})for x in ['a','b']], 'one_success'),
'flags':("c('environment.create',id='e');c('flag.create',environment='e',id='f',default=False)", [('flag.update',{'environment':'e','id':'f','expected_revision':1,'enabled':x,'rules':[]})for x in [True,False]], 'one_success'),
'outbox':("c('queue.create',id='q',max_attempts=2,retry_delay=0);c('message.publish',queue='q',id='m',payload=1,key='m')", [('claim',{'queue':'q','worker':x,'now':0,'lease':10,'limit':1})for x in ['a','b']], 'one_acquired'),
'subscriptions':("c('plan.put',id='p',price=100,period=10);c('subscriber.create',id='s',plan='p',start=0)", [('bill',{'id':'s','now':10,'key':x})for x in ['a','b']], 'one_invoice'),
'timesheets':("c('project.put',id='p',budget=100,rate=1);c('worker.put',id='a',role='worker');c('worker.put',id='b',role='worker');c('worker.put',id='m',role='manager');c('entry.create',id='a',worker='a',project='p',start=0,end=80,note='a');c('entry.create',id='b',worker='b',project='p',start=0,end=80,note='b');c('entry.submit',id='a',expected_revision=1);c('entry.submit',id='b',expected_revision=1)", [('entry.review',{'id':x,'actor':'m','approve':True,'expected_revision':2})for x in ['a','b']], 'one_success'),
'documents':("c('document.create',id='d',fields={'x':'a'})", [('document.edit',{'id':'d','expected_revision':1,'changes':{'x':x}})for x in ['b','c']], 'one_success'),
'warehouse':("c('product.put',id='p',name='P');c('lot.receive',id='l',product='p',quantity=100,expires=10,key='l');c('order.create',id='a',lines=[{'product':'p','quantity':80}]);c('order.create',id='b',lines=[{'product':'p','quantity':80}])", [('order.allocate',{'id':x,'now':0})for x in ['a','b']], 'one_success'),
'annotations':("c('dataset.create',id='d',labels=['x'],reviews=1);c('annotator.put',id='a',active=True);c('annotator.put',id='b',active=True);c('item.add',dataset='d',id='i',payload=1)", [('claim',{'dataset':'d','annotator':x,'now':0,'lease':10})for x in ['a','b']], 'one_nonnull'),
'vault':("c('workspace.create',id='w',owner='a',quota=100);c('document.put',workspace='w',actor='a',id='d',content='old',expected_revision=0)", [('document.put',{'workspace':'w','actor':'a','id':'d','content':x,'expected_revision':1})for x in ['x','y']], 'one_success'),
'etl':("c('schema.put',id='s',columns=[{'name':'id','type':'text','required':True}],key='id');c('job.create',id='j',schema='s',csv=chr(10).join(['id','x','']));c('job.run',id='j',key='run')", [('job.publish',{'id':'j','expected_revision':1})for _ in range(2)], 'one_success'),
'loyalty':("c('member.create',id='m');c('earn',member='m',id='l',points=100,expires=20,key='l')", [('hold',{'member':'m','id':x,'points':80,'now':0,'ttl':10})for x in ['a','b']], 'one_success'),
'manufacturing':("c('part.put',id='p',name='P',cost=1);c('part.put',id='a',name='A',cost=0);c('bom.put',product='a',components=[{'part':'p','quantity':1}]);c('receive',part='p',quantity=100,key='p');c('work.create',id='x',product='a',quantity=80);c('work.create',id='y',product='a',quantity=80)", [('work.reserve',{'id':x})for x in ['x','y']], 'one_success'),
'voting':("c('member.put',id='a',active=True);c('poll.create',id='p',candidates=['X','Y'],quorum=1);c('poll.open',id='p',expected_revision=1)", [('vote',{'poll':'p','member':'a','ranking':[x],'key':x})for x in ['X','Y']], 'one_success'),
}


def program(name):
 setup,calls,mode=RACES[name]
 return f'''
 business_db=db
 for attempt in range(3):
  db=Path(tmp)/('race-'+str(attempt)+'.json')
  {setup}
  packets={calls!r}
  workers=[]
  try:
   for operation,data in packets:
    code="import json,sys;from app import Service;s=Service(sys.argv[1]);print('READY',flush=True);sys.stdin.readline();op,data=json.loads(sys.argv[2]);\\ntry:r=s.call(op,data);print(json.dumps({{'ok':True,'result':r}}),flush=True)\\nexcept ValueError as e:print(json.dumps({{'ok':False,'error':str(e)}}),flush=True)"
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
   for p in workers:p.stdin.write('go\\n');p.stdin.flush()
   results=[]
   for p in workers:
    out,err=p.communicate(timeout=10);assert p.returncode==0,err
    results.append(json.loads(out))
   mode={mode!r}
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
'''
