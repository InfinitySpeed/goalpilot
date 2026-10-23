from goalpilot_runtime import ReplayService, require, text, integer, fields, sequence, idempotent, dag

def banner():return 'Local Ops — café'

class Service(ReplayService):
 def initial(self):return {'parts':{},'boms':{},'works':{},'keys':{}}
 def handle(self,s,op,d):
  parts,boms,works=s['parts'],s['boms'],s['works']
  def record(m,k):
   text(k);require(k in m,'Missing record');return m[k]
  def reserved(p):return sum(x['quantity'] for w in works.values() for x in w['reserved'] if x['part']==p)
  def stock(p):
   r=record(parts,p);n=reserved(p);return {'on_hand':r['on_hand'],'reserved':n,'available':r['on_hand']-n}
  def public(w):return {k:v for k,v in w.items() if k!='snapshot'}
  positive=lambda x:integer(x,minimum=1)
  if op=='part.put':
   fields(d,{'id':text,'name':text,'cost':integer})
   old=parts.get(d['id'],{'on_hand':0});parts[d['id']]={**d,'on_hand':old['on_hand']};return dict(parts[d['id']])
  if op=='bom.put':
   fields(d,{'product':text,'components':sequence(lambda x:fields(x,{'part':text,'quantity':positive}),nonempty=True)})
   record(parts,d['product']);cs={}
   for c in d['components']:
    record(parts,c['part']);cs[c['part']]=cs.get(c['part'],0)+c['quantity']
   graph={p:[c['part'] for c in b['components']] for p,b in boms.items()};graph[d['product']]=sorted(cs)
   for p in parts:graph.setdefault(p,[])
   dag(graph)
   b={'product':d['product'],'components':[{'part':p,'quantity':q} for p,q in sorted(cs.items())],'revision':boms.get(d['product'],{}).get('revision',0)+1};boms[d['product']]=b;return b
  if op=='receive':
   fields(d,{'part':text,'quantity':positive,'key':text});record(parts,d['part'])
   def receive():
    parts[d['part']]['on_hand']+=d['quantity'];return {'on_hand':parts[d['part']]['on_hand']}
   return idempotent(s,d['key'],op,d,receive)
  if op=='receive.import':
   fields(d,{'receipts':sequence(lambda x:fields(x,{'part':text,'quantity':positive,'key':text}))})
   for receipt in d['receipts']:self.handle(s,'receive',receipt)
   return {'imported':len(d['receipts'])}
  if op=='stock':fields(d,{'part':text});return stock(d['part'])
  if op=='work.create':
   fields(d,{'id':text,'product':text,'quantity':positive});require(d['id'] not in works,'Duplicate work');b=record(boms,d['product'])
   w={**d,'produced':0,'scrapped':0,'status':'draft','reserved':[],'cost':0,'snapshot':[{**c,'cost':parts[c['part']]['cost']} for c in b['components']]};works[d['id']]=w;return public(w)
  if op=='work.list':
   fields(d,{},optional={'status':text});require('status' not in d or d['status'] in ('draft','confirmed','partial','complete','cancelled'),'Invalid status')
   return [public(w) for k,w in sorted(works.items()) if 'status' not in d or w['status']==d['status']]
  if op in ('work.get','work.reserve','work.cancel'):
   fields(d,{'id':text});w=record(works,d['id'])
   if op=='work.get':return public(w)
   if op=='work.reserve':
    if w['status']=='confirmed':return public(w)
    require(w['status']=='draft','Cannot reserve')
    rs=[{'part':c['part'],'quantity':c['quantity']*w['quantity']} for c in w['snapshot']]
    require(all(stock(c['part'])['available']>=c['quantity'] for c in rs),'Insufficient stock');w['reserved']=rs;w['status']='confirmed'
   else:
    require(w['status']!='complete','Cannot cancel complete');w['reserved']=[];w['status']='cancelled'
   return public(w)
  if op=='work.finish':
   fields(d,{'id':text,'good':integer,'scrap':integer,'key':text});w=record(works,d['id'])
   def finish():
    n=d['good']+d['scrap'];require(w['status'] in ('confirmed','partial'),'Cannot finish');require(0<n<=w['quantity']-w['produced']-w['scrapped'],'Invalid quantity')
    for c,r in zip(w['snapshot'],w['reserved']):
     used=c['quantity']*n;parts[c['part']]['on_hand']-=used;r['quantity']-=used;w['cost']+=used*c['cost']
    parts[w['product']]['on_hand']+=d['good'];w['produced']+=d['good'];w['scrapped']+=d['scrap'];w['status']='complete' if w['produced']+w['scrapped']==w['quantity'] else 'partial'
    if w['status']=='complete':w['reserved']=[]
    return public(w)
   return idempotent(s,d['key'],op,d,finish)
  raise ValueError('Unknown operation')

if __name__=='__main__':Service.main()
