from goalpilot_runtime import ReplayService, require, fields, text, integer, sequence, idempotent, get_record


def banner(): return 'Local Ops — café'


class Service(ReplayService):
 def initial(self): return dict(members={}, lots={}, holds={}, keys={}, history=[])

 def handle(self,s,op,d):
  pos=lambda x: integer(x,minimum=1)
  schemas={
   'member.create':{'id':text},
   'earn':{'member':text,'id':text,'points':pos,'expires':integer,'key':text},
   'balance':{'member':text,'now':integer},
   'hold':{'member':text,'id':text,'points':pos,'now':integer,'ttl':pos},
   'redeem':{'id':text,'now':integer,'key':text},
   'release':{'id':text,'now':integer},
   'refund':{'id':text,'points':pos,'now':integer,'key':text},
   'lot.list':{'member':text},'hold.get':{'id':text,'now':integer},
   'history':{'member':text},'earn.import':{'earnings':sequence(lambda x: fields(x,schemas['earn']))}}
  require(op in schemas,'Unknown operation')
  fields(d,schemas[op])
  if op=='earn.import':
   for earning in d['earnings']: self.handle(s,'earn',earning)
   return {'imported':len(d['earnings'])}
  # Replays precede lazy expiry, so the original snapshot always wins.
  if op in ('earn','redeem','refund'):
   return idempotent(s,d['key'],op,d,lambda:self.apply(s,op,d))
  return self.apply(s,op,d)

 def apply(self,s,op,d):
  lots=s['lots']; holds=s['holds']
  if 'now' in d:
   for h in holds.values():
    if h['status']=='held' and h['expires']<=d['now']: h['status']='expired'
  if op=='member.create':
   require(d['id'] not in s['members'],'Duplicate member')
   s['members'][d['id']]={'id':d['id']}
   return s['members'][d['id']]
  if 'member' in d: get_record(s['members'],d['member'])
  def member_lots(): return sorted((l for l in lots.values() if l['member']==d['member']),key=lambda l:(l['expires'],l['id']))
  def reserved(lot): return sum(a['points'] for h in holds.values() if h['status']=='held' for a in h['allocations'] if a['lot']==lot)
  def snapshot(h): return {k:h[k] for k in ('id','member','points','status','refunded')}
  if op=='earn':
   require(d['id'] not in lots,'Duplicate lot')
   l={k:d[k] for k in ('id','member','points','expires')}; l['remaining']=d['points']; lots[l['id']]=l
   s['history'].append({'member':d['member'],'kind':'earn','id':d['id'],'points':d['points']})
   return l
  if op=='lot.list': return member_lots()
  if op=='history': return [{k:e[k] for k in ('kind','id','points')} for e in s['history'] if e['member']==d['member']]
  if op=='balance':
   available=expired=held=0
   for l in member_lots():
    r=reserved(l['id']); held+=r
    if l['expires']>d['now']: available+=l['remaining']-r
    else: expired+=l['remaining']-r
   return dict(available=available,held=held,expired=expired)
  if op=='hold':
   require(d['id'] not in holds,'Duplicate hold')
   left=d['points']; allocations=[]
   for l in member_lots():
    if l['expires']<=d['now']: continue
    n=min(left,l['remaining']-reserved(l['id']))
    if n: allocations.append({'lot':l['id'],'points':n}); left-=n
    if not left: break
   require(left==0,'Insufficient points')
   h=dict(id=d['id'],member=d['member'],points=d['points'],status='held',expires=d['now']+d['ttl'],allocations=allocations)
   holds[h['id']]=h
   return h
  h=get_record(holds,d['id'])
  if op=='hold.get': return h
  if op=='release':
   require(h['status'] in ('held','released'),'Hold is not held')
   h['status']='released'; return h
  if op=='redeem':
   require(h['status']=='held','Hold is not held')
   for a in h['allocations']: lots[a['lot']]['remaining']-=a['points']
   h['status']='redeemed'; h['refunded']=0
  elif op=='refund':
   require(h['status']=='redeemed','Hold is not redeemed')
   require(h['refunded']+d['points']<=h['points'],'Excess refund')
   # Skip quantities already refunded at the tail of the allocation list.
   skip=h['refunded']; left=d['points']
   for a in reversed(h['allocations']):
    used=min(skip,a['points']); skip-=used
    n=min(left,a['points']-used); lots[a['lot']]['remaining']+=n; left-=n
   h['refunded']+=d['points']
  s['history'].append(dict(member=h['member'],kind=op,id=h['id'],points=d.get('points',h['points'])))
  return snapshot(h)


if __name__=='__main__': Service.main()
