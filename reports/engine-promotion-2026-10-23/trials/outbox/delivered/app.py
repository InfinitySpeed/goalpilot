from goalpilot_runtime import ReplayService, require, fields, text, integer, choice, idempotent, get_record

def banner():return 'Local Ops — café'

def nonnegative(x): integer(x)
def positive(x): integer(x,minimum=1)
def signed(x): require(type(x) is int)
def json_value(x):
 import json
 try: json.dumps(x,allow_nan=False)
 except (TypeError,ValueError): raise ValueError('Invalid JSON value')
 require(x is None or type(x) in (str,int,float,bool,list,dict))
 if isinstance(x,dict):
  require(all(type(k) is str for k in x)); [json_value(v) for v in x.values()]
 if isinstance(x,list): [json_value(v) for v in x]

class Service(ReplayService):
 def initial(self): return {'queues':{},'messages':{},'keys':{},'receipts':[]}
 def handle(self,s,op,d):
  def schema(required,optional=None): fields(d,required,optional)
  def queue(): return get_record(s['queues'],d['queue'])
  def message():
   queue(); return get_record(s['messages'][d['queue']],d['id'])
  def clear(m): m['receipt']=None; m['worker']=None; m.pop('expires',None)
  def release(m,q,now):
   m['status']='dead' if m['attempts']>=q['max_attempts'] else 'pending'
   if m['status']=='pending': m['not_before']=now+q['retry_delay']
   clear(m)
  def expire(q):
   for m in s['messages'][d['queue']].values():
    if m['status']=='leased' and d['now']>=m['expires']: release(m,q,d['now'])
  def publish(data):
   fields(data,{'queue':text,'id':text,'payload':json_value,'key':text},{'priority':signed,'not_before':nonnegative})
   get_record(s['queues'],data['queue'])
   n=dict(data,priority=data.get('priority',0),not_before=data.get('not_before',0))
   def insert():
    messages=s['messages'][n['queue']]; require(n['id'] not in messages,'Duplicate message')
    m={k:n[k] for k in ('id','queue','payload','priority','not_before')}
    m.update(status='pending',attempts=0,receipt=None,worker=None); messages[m['id']]=m
    return m
   return idempotent(s,n['key'],'message.publish',n,insert)
  if op=='queue.create':
   schema({'id':text,'max_attempts':positive,'retry_delay':nonnegative}); require(d['id'] not in s['queues'],'Duplicate queue')
   s['queues'][d['id']]=dict(d); s['messages'][d['id']]={}; return dict(d)
  if op=='message.publish': return publish(d)
  if op=='publish.import':
   schema({'messages':lambda x:require(type(x) is list)})
   for item in d['messages']: publish(item)
   return {'imported':len(d['messages'])}
  if op=='message.get':
   schema({'queue':text,'id':text}); return message()
  if op=='message.list':
   schema({'queue':text},{'status':choice('pending','leased','done','dead','cancelled')}); queue()
   return [m for _,m in sorted(s['messages'][d['queue']].items()) if 'status' not in d or m['status']==d['status']]
  if op=='message.cancel':
   schema({'queue':text,'id':text}); m=message(); require(m['status']=='pending'); m['status']='cancelled'; return m
  if op=='redrive':
   schema({'queue':text,'id':text,'now':nonnegative}); m=message(); require(m['status']=='dead')
   m.update(status='pending',attempts=0,not_before=d['now']); return m
  if op in ('ack','nack'):
   schema({'queue':text,'id':text,'receipt':text,'now':nonnegative}); m=message(); q=queue()
   require(m['status']=='leased' and m['receipt']==d['receipt'] and d['now']<m['expires'],'Invalid lease')
   if op=='nack': release(m,q,d['now'])
   else: m['status']='done'; clear(m)
   return m
  if op=='queue.stats':
   schema({'queue':text,'now':nonnegative}); q=queue(); expire(q)
   return {status:sum(m['status']==status for m in s['messages'][d['queue']].values()) for status in ('pending','leased','done','dead','cancelled')}
  if op=='claim':
   schema({'queue':text,'worker':text,'now':nonnegative,'lease':positive,'limit':lambda x:integer(x,minimum=1,maximum=100)})
   q=queue(); expire(q)
   eligible=sorted((m for m in s['messages'][d['queue']].values() if m['status']=='pending' and m['not_before']<=d['now']),key=lambda m:(-m['priority'],m['id']))[:d['limit']]
   for m in eligible:
    receipt=self.opaque(); require(receipt not in s['receipts']); s['receipts'].append(receipt)
    m.update(status='leased',attempts=m['attempts']+1,receipt=receipt,worker=d['worker'],expires=d['now']+d['lease'])
   return eligible
  raise ValueError('Unknown operation')

if __name__=='__main__': Service.main()
