from goalpilot_runtime import ReplayService, require, fields, text, integer, sequence, choice, get_record, compare_revision, idempotent

def banner():return 'Local Ops — café'

positive=lambda x: integer(x,minimum=1)
line=fields if False else None

def check_line(x):
 fields(x,{'description':text,'quantity':positive,'unit_cents':integer})
 return x

def payment(x):
 fields(x,{'id':text,'amount':positive,'key':text})
 return x

class Service(ReplayService):
 def initial(self):return {'customers':{},'invoices':{},'keys':{}}
 def handle(self,s,op,d):
  if op=='customer.put':
   fields(d,{'id':text,'name':text}); s['customers'][d['id']]=dict(d); return s['customers'][d['id']]
  if op=='customer.list':
   fields(d,{}); return [s['customers'][k] for k in sorted(s['customers'])]
  if op=='invoice.create':
   fields(d,{'id':text,'customer':text,'lines':sequence(check_line,nonempty=True),'tax_bps':lambda x:integer(x,maximum=10000)})
   require(d['id'] not in s['invoices'],'Invoice exists'); get_record(s['customers'],d['customer'])
   subtotal=sum(x['quantity']*x['unit_cents'] for x in d['lines']); tax=(subtotal*d['tax_bps']+5000)//10000
   r={k:d[k] for k in ('id','customer','lines')}
   r.update(status='draft',subtotal=subtotal,tax=tax,total=subtotal+tax,paid=0,credited=0,balance=subtotal+tax,revision=1)
   s['invoices'][d['id']]=r; return r
  if op=='invoice.get':
   fields(d,{'id':text}); return get_record(s['invoices'],d['id'])
  if op=='invoice.list':
   fields(d,{},optional={'customer':text,'status':choice('draft','issued','partial','paid','credited','void')})
   return [r for _,r in sorted(s['invoices'].items()) if all(r[k]==v for k,v in d.items())]
  if op in ('invoice.issue','invoice.void'):
   fields(d,{'id':text,'expected_revision':positive}); r=get_record(s['invoices'],d['id']); compare_revision(r,d['expected_revision'])
   if op=='invoice.issue':require(r['status']=='draft','Must be draft'); r['status']='issued'
   else:
    require(r['status'] in ('draft','issued') and r['paid']==r['credited']==0,'Cannot void'); r.update(status='void',balance=0)
   r['revision']+=1; return r
  if op in ('invoice.pay','invoice.credit'):
   payment(d)
   def apply():
    r=get_record(s['invoices'],d['id']); credit=op=='invoice.credit'
    require(r['status'] in (('issued','partial','paid') if credit else ('issued','partial')),'Invalid status')
    require(d['amount']<=r['balance'],'Amount exceeds balance')
    if credit:require(d['amount']<=r['total']-r['credited'],'Excess credit')
    r['credited' if credit else 'paid']+=d['amount']; r['balance']=r['total']-r['paid']-r['credited']
    r['status']=('credited' if credit and r['paid']==0 else 'paid') if r['balance']==0 else 'partial'
    r['revision']+=1; return r
   return idempotent(s,d['key'],op,d,apply)
  if op=='payment.import':
   fields(d,{'payments':sequence(payment)})
   for p in d['payments']:self.handle(s,'invoice.pay',p)
   return {'imported':len(d['payments'])}
  if op=='statement':
   fields(d,{'customer':text}); get_record(s['customers'],d['customer'])
   rows=[r for r in s['invoices'].values() if r['customer']==d['customer']]
   return {'invoiced':sum(r['total'] for r in rows if r['status']!='void'),'paid':sum(r['paid'] for r in rows),'credited':sum(r['credited'] for r in rows),'due':sum(r['balance'] for r in rows)}
  raise ValueError('Unknown operation')

if __name__=='__main__':Service.main()
