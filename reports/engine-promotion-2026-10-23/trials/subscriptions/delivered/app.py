from goalpilot_runtime import ReplayService, require, fields, text, integer, get_record, compare_revision, idempotent, sequence

def banner():return 'Local Ops — café'

nat=lambda x:integer(x)
pos=lambda x:integer(x,minimum=1)

class Service(ReplayService):
 def initial(self):return {'plans':{},'subscribers':{},'invoices':{},'keys':{}}
 def handle(self,s,op,d):
  schemas={
   'plan.put':{'id':text,'price':nat,'period':pos},
   'subscriber.create':{'id':text,'plan':text,'start':nat},
   'subscriber.get':{'id':text},'invoice.list':{'subscriber':text},
   'bill':{'id':text,'now':nat,'key':text},
   'invoice.pay':{'id':text,'amount':pos,'key':text},
   'subscriber.change':{'id':text,'plan':text,'now':nat,'expected_revision':pos},
   'subscriber.cancel':{'id':text,'expected_revision':pos},
   'invoice.import_payments':{'payments':sequence(lambda v:fields(v,{'id':text,'amount':pos,'key':text}))},
   'report':{}}
  require(op in schemas,'Unknown operation');fields(d,schemas[op])
  def sub(i):return get_record(s['subscribers'],i)
  def inv(i):return get_record(s['invoices'],i)
  def status(a):
   a['balance']=sum(v['amount']-v['paid'] for v in s['invoices'].values() if v['subscriber']==a['id'])
   if a['status']!='cancelled':a['status']='past_due' if a['balance'] else 'active'
  def invoice(a,due,amount):
   v={'id':self.opaque(),'subscriber':a['id'],'due':due,'amount':amount,'paid':0};s['invoices'][v['id']]=v;return v
  if op=='plan.put':
   s['plans'][d['id']]=dict(d);return s['plans'][d['id']]
  if op=='subscriber.create':
   require(d['id'] not in s['subscribers'],'Subscriber exists');p=get_record(s['plans'],d['plan'])
   a=dict(id=d['id'],plan=d['plan'],status='active',start=d['start'],period_end=d['start']+p['period'],price=p['price'],period=p['period'],cancel_at_end=False,balance=0,revision=1)
   s['subscribers'][a['id']]=a;return a
  if op=='subscriber.get':return sub(d['id'])
  if op=='invoice.list':
   sub(d['subscriber']);return sorted([v for v in s['invoices'].values() if v['subscriber']==d['subscriber']],key=lambda v:(v['due'],v['id']))
  if op in ('bill','invoice.pay'):
   def apply():
    if op=='invoice.pay':
     v=inv(d['id']);require(d['amount']<=v['amount']-v['paid'],'Overpayment');v['paid']+=d['amount'];status(sub(v['subscriber']));return v
    a=sub(d['id']);require(a['status'] in ('active','past_due'),'Cancelled');require(d['now']>=a['period_end'],'Period not reached');rows=[]
    while a['period_end']<=d['now']:
     if a['cancel_at_end']:a['status']='cancelled';break
     rows.append(invoice(a,a['period_end'],a['price']));a['start']=a['period_end'];a['period_end']+=a['period']
    status(a);return {'invoices':rows,'subscriber':a}
   return idempotent(s,d['key'],op,d,apply)
  if op=='subscriber.cancel':
   a=sub(d['id']);compare_revision(a,d['expected_revision']);require(a['status'] in ('active','past_due'),'Cancelled');a['cancel_at_end']=True;a['revision']+=1;return a
  if op=='subscriber.change':
   a=sub(d['id']);compare_revision(a,d['expected_revision']);p=get_record(s['plans'],d['plan'])
   require(a['status']=='active' and a['start']<=d['now']<a['period_end'],'Invalid change time/status');require(p['period']==a['period'],'Period mismatch')
   adjustment=(p['price']-a['price'])*(a['period_end']-d['now'])//a['period']
   if adjustment>0:invoice(a,d['now'],adjustment)
   elif adjustment<0:
    credit=-adjustment
    for v in sorted(s['invoices'].values(),key=lambda v:(v['due'],v['id'])):
     if v['subscriber']==a['id']:
      n=min(credit,v['amount']-v['paid']);v['amount']-=n;credit-=n
   a['price']=p['price'];a['plan']=p['id'];a['revision']+=1;status(a);return {'subscriber':a,'adjustment':adjustment}
  if op=='invoice.import_payments':
   for payment in d['payments']:self.handle(s,'invoice.pay',payment)
   return {'imported':len(d['payments'])}
  if op=='report':
   vals=list(s['subscribers'].values());invoices=list(s['invoices'].values())
   return dict(subscribers=len(vals),**{k:sum(a['status']==k for a in vals) for k in ('active','past_due','cancelled')},invoiced=sum(v['amount'] for v in invoices),collected=sum(v['paid'] for v in invoices),outstanding=sum(v['amount']-v['paid'] for v in invoices))

if __name__=='__main__':Service.main()
