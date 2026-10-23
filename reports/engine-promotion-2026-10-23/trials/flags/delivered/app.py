import hashlib
from goalpilot_runtime import ReplayService, require, text, integer, boolean, fields, sequence, nullable

def banner():return 'Local Ops — café'

class Service(ReplayService):
 def initial(self):return {'environments':{}}
 def handle(self,s,op,d):
  t=text; i=integer; b=boolean
  if op=='environment.create':
   fields(d,{'id':t}); require(d['id'] not in s['environments'],'Environment exists')
   s['environments'][d['id']]={'segments':{},'flags':{},'audit':[]}
   return {'id':d['id']}
  require(op in ('segment.put','segment.delete','flag.create','flag.update','flag.publish','flag.evaluate','flag.rollback','flag.get','flag.list','audit.list','flag.import'),'Unknown operation')
  schemas={
   'segment.put':{'id':t,'members':sequence(t)},'segment.delete':{'id':t},
   'flag.create':{'id':t,'default':b},'flag.update':{'id':t,'expected_revision':lambda v:i(v,1),'enabled':b,'rules':sequence(lambda r:fields(r,{'segment':nullable(t),'percent':lambda v:i(v,0,100),'value':b}))},
   'flag.publish':{'id':t,'expected_revision':lambda v:i(v,1)},'flag.evaluate':{'id':t,'user':t},
   'flag.rollback':{'id':t,'revision':lambda v:i(v,1),'expected_revision':lambda v:i(v,1)},
   'flag.get':{'id':t},'flag.list':{},'audit.list':{},
   'flag.import':{'flags':sequence(lambda f:fields(f,{'id':t,'default':b}))}}
  fields(d,{'environment':t,**schemas[op]})
  env=d['environment']; require(env in s['environments'],'Unknown environment'); e=s['environments'][env]
  fs=e['flags']; seg=e['segments']
  def event(kind,f):e['audit'].append({'sequence':len(e['audit'])+1,'kind':'flag.'+kind,'flag':f['id'],'revision':f['revision']})
  def create(v):
   require(v['id'] not in fs,'Flag exists')
   f={'id':v['id'],'environment':env,'revision':1,'published':0,'enabled':False,'default':v['default'],'rules':[]}
   fs[v['id']]={'draft':f,'history':{}}; event('created',f); return f
  if op=='flag.list':return [fs[k]['draft'] for k in sorted(fs)]
  if op=='audit.list':return e['audit']
  if op=='flag.import':
   ids=[f['id'] for f in d['flags']]; require(len(ids)==len(set(ids)) and not any(k in fs for k in ids),'Duplicate flag')
   for v in d['flags']:create(v)
   return {'imported':len(ids)}
  if op=='flag.create':return create(d)
  if op=='segment.put':
   seg[d['id']]=sorted(set(d['members'])); return {'id':d['id'],'environment':env,'members':seg[d['id']]}
  if op=='segment.delete':
   require(d['id'] in seg,'Unknown segment')
   for rec in fs.values():
    for f in [rec['draft'],*rec['history'].values()]:require(not any(r['segment']==d['id'] for r in f['rules']),'Segment referenced')
   del seg[d['id']]; return {'deleted':d['id']}
  require(d['id'] in fs,'Unknown flag'); rec=fs[d['id']]; f=rec['draft']; h=rec['history']
  if op=='flag.get':return f
  if op=='flag.evaluate':
   bucket=int.from_bytes(hashlib.sha256((env+'|'+d['id']+'|'+d['user']).encode()).digest()[:8],'big')%100
   live=h.get(str(f['published'])); value=f['default'] if live is None else live['default']
   if live and live['enabled']:
    for r in live['rules']:
     if (r['segment'] is None or d['user'] in seg[r['segment']]) and bucket<r['percent']:value=r['value']; break
   return {'value':value,'revision':f['published'],'bucket':bucket}
  require(d['expected_revision']==f['revision'],'Stale revision')
  if op=='flag.update':
   require(all(r['segment'] is None or r['segment'] in seg for r in d['rules']),'Unknown segment')
   f.update(revision=f['revision']+1,enabled=d['enabled'],rules=d['rules']); event('updated',f)
  elif op=='flag.publish':
   if f['published']!=f['revision']:
    f['published']=f['revision']; h[str(f['revision'])]=dict(f); event('published',f)
  else:
   require(str(d['revision']) in h,'Unknown historic revision'); old=h[str(d['revision'])]
   f={**old,'revision':f['revision']+1}; f['published']=f['revision']; rec['draft']=f; h[str(f['revision'])]=dict(f); event('rolled_back',f)
  return f

if __name__=='__main__':Service.main()
