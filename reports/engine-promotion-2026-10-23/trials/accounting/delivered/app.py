from goalpilot_runtime import ReplayService, require, fields, text, integer, choice, sequence, idempotent, get_record, compare_revision

def banner():return 'Local Ops — café'

class Service(ReplayService):
 def initial(self):return {'accounts':{},'periods':{},'entries':{},'keys':{}}
 def handle(self,s,op,d):
  natural=lambda x:integer(x)
  signed=lambda x:require(type(x) is int,'Integer required')
  line=lambda x:fields(x,{'account':text,'debit':natural,'credit':natural})
  post=lambda x:fields(x,{'id':text,'date':signed,'lines':sequence(line,nonempty=True),'key':text})
  def period(date):
   matches=[p for p in s['periods'].values() if p['start']<=date<p['end']]
   require(len(matches)==1 and matches[0]['status']=='open','Date outside open period')
   return matches[0]['id']
  def add(payload):
   require(payload['id'] not in s['entries'],'Duplicate entry')
   lines=payload['lines'];require(len(lines)>=2,'Two lines required')
   for l in lines:
    get_record(s['accounts'],l['account']);require((l['debit']>0) != (l['credit']>0),'One positive side required')
   require(sum(l['debit'] for l in lines)==sum(l['credit'] for l in lines)>0,'Unbalanced entry')
   e={'id':payload['id'],'date':payload['date'],'period':period(payload['date']),'lines':lines,'status':'posted','reversal':None}
   s['entries'][e['id']]=e
   return e
  def posting(payload):
   post(payload)
   return idempotent(s,payload['key'],'journal.post',payload,lambda:add(payload))
  if op=='account.create':
   fields(d,{'id':text,'name':text,'kind':choice('asset','liability','income','expense')})
   require(d['id'] not in s['accounts'],'Duplicate account');s['accounts'][d['id']]=dict(d);return s['accounts'][d['id']]
  if op=='period.create':
   fields(d,{'id':text,'start':natural,'end':signed})
   require(d['id'] not in s['periods'] and d['end']>d['start'],'Invalid period')
   require(all(d['end']<=p['start'] or d['start']>=p['end'] for p in s['periods'].values()),'Overlapping period')
   p=dict(d,status='open',revision=1);s['periods'][d['id']]=p;return p
  if op in ('period.close','period.reopen'):
   fields(d,{'id':text,'expected_revision':natural});p=get_record(s['periods'],d['id']);compare_revision(p,d['expected_revision'])
   require(p['status']==('open' if op=='period.close' else 'closed'),'Invalid period status')
   p['status']='closed' if op=='period.close' else 'open';p['revision']+=1;return p
  if op=='journal.post':return posting(d)
  if op=='journal.import':
   fields(d,{'entries':sequence(post)})
   for e in d['entries']:posting(e)
   return {'imported':len(d['entries'])}
  if op=='journal.reverse':
   fields(d,{'id':text,'reversal_id':text,'date':signed,'key':text})
   def reverse():
    e=get_record(s['entries'],d['id'])
    require(e['status']=='posted' and not any(x['reversal']==e['id'] for x in s['entries'].values()),'Cannot reverse entry')
    r=add({'id':d['reversal_id'],'date':d['date'],'lines':[{'account':l['account'],'debit':l['credit'],'credit':l['debit']} for l in e['lines']]})
    e['status']='reversed';e['reversal']=r['id'];return r
   return idempotent(s,d['key'],op,d,reverse)
  if op=='journal.get':
   fields(d,{'id':text});return get_record(s['entries'],d['id'])
  if op=='journal.list':
   fields(d,{},optional={'period':text,'account':text})
   if 'period' in d:get_record(s['periods'],d['period'])
   if 'account' in d:get_record(s['accounts'],d['account'])
   return sorted([e for e in s['entries'].values() if ('period' not in d or e['period']==d['period']) and ('account' not in d or any(l['account']==d['account'] for l in e['lines']))],key=lambda e:(e['date'],e['id']))
  def balance(a):
   ls=[l for e in s['entries'].values() for l in e['lines'] if l['account']==a]
   debit=sum(l['debit'] for l in ls);credit=sum(l['credit'] for l in ls)
   return {'debit':debit,'credit':credit,'net':debit-credit}
  if op=='account.balance':
   fields(d,{'id':text});get_record(s['accounts'],d['id']);return balance(d['id'])
  if op=='trial_balance':
   fields(d,{});return [dict(account=a,**balance(a)) for a in sorted(s['accounts'])]
  raise ValueError('Unknown operation')

if __name__=='__main__':Service.main()
