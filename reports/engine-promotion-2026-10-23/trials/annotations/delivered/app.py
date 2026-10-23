from goalpilot_runtime import ReplayService, require, fields, text, integer, boolean, identifiers


def banner():return 'Local Ops — café'

class Service(ReplayService):
 def initial(self):return {'datasets':{},'annotators':{}}
 def handle(self,s,op,d):
  pos=lambda x:integer(x,minimum=1)
  def schema(req,opt=None):fields(d,req,opt)
  def dataset():
   require(d['dataset'] in s['datasets'],'Unknown dataset')
   return s['datasets'][d['dataset']]
  def item(ds,key='id'):
   require(d[key] in ds['items'],'Unknown item')
   return ds['items'][d[key]]
  def active():require(s['annotators'].get(d['annotator']) is True,'Inactive or unknown annotator')
  def public(i):return {k:v for k,v in i.items() if k not in ('claims','history')}
  if op=='dataset.create':
   schema({'id':text,'labels':lambda x:identifiers(x,nonempty=True),'reviews':pos})
   require(d['id'] not in s['datasets'],'Duplicate dataset')
   ds={'id':d['id'],'labels':identifiers(d['labels'],nonempty=True),'reviews':d['reviews'],'items':{}}
   s['datasets'][d['id']]=ds
   return {k:v for k,v in ds.items() if k!='items'}
  if op=='annotator.put':
   schema({'id':text,'active':boolean});s['annotators'][d['id']]=d['active'];return dict(d)
  if op in ('item.add','item.import'):
   if op=='item.add':schema({'dataset':text,'id':text,'payload':lambda x:None});rows=[{'id':d['id'],'payload':d['payload']}]
   else:
    schema({'dataset':text,'items':lambda x:require(isinstance(x,list))});rows=d['items']
   ds=dataset();seen=set()
   for r in rows:
    fields(r,{'id':text,'payload':lambda x:None});require(r['id'] not in seen and r['id'] not in ds['items'],'Duplicate item');seen.add(r['id'])
   for r in rows:ds['items'][r['id']]={'id':r['id'],'dataset':d['dataset'],'payload':r['payload'],'status':'pending','votes':[],'revision':1,'consensus':None,'claims':{},'history':[]}
   return public(ds['items'][d['id']]) if op=='item.add' else {'imported':len(rows)}
  if op=='claim':
   schema({'dataset':text,'annotator':text,'now':integer,'lease':pos});ds=dataset();active();a=d['annotator'];now=d['now']
   for key in sorted(ds['items']):
    i=ds['items'][key];live={a:c for a,c in i['claims'].items() if c['expires']>now}
    if i['status']=='complete' or any(v['annotator']==a for v in i['votes']) or a in live or len(i['votes'])+len(live)>=ds['reviews']:continue
    receipt=self.opaque();i['claims']=live;i['claims'][a]={'receipt':receipt,'expires':now+d['lease']}
    return {'item':public(i),'receipt':receipt,'expires':now+d['lease']}
   return None
  if op=='submit':
   schema({'dataset':text,'item':text,'annotator':text,'receipt':text,'now':integer,'label':text});ds=dataset();i=item(ds,'item');active();a=d['annotator'];c=i['claims'].get(a)
   require(d['label'] in ds['labels'],'Unknown label');require(c is not None and c['receipt']==d['receipt'] and d['now']<c['expires'],'Invalid claim')
   require(i['status']!='complete' and not any(v['annotator']==a for v in i['votes']),'Already voted')
   i['votes'].append({'annotator':a,'label':d['label']});del i['claims'][a];i['revision']+=1
   i['status']='complete' if len(i['votes'])==ds['reviews'] else 'reviewing'
   i['consensus']=i['votes'][0]['label'] if i['status']=='complete' and len({v['label'] for v in i['votes']})==1 else None
   return public(i)
  if op=='item.reopen':
   schema({'dataset':text,'id':text,'expected_revision':integer});i=item(dataset());require(i['status']=='complete' and i['revision']==d['expected_revision'],'Invalid revision or status')
   i['history'].append({'votes':i['votes'],'consensus':i['consensus']});i.update(votes=[],claims={},consensus=None,status='pending',revision=i['revision']+1);return public(i)
  if op in ('item.get','history'):
   schema({'dataset':text,'id':text});i=item(dataset());return public(i) if op=='item.get' else i['history']
  if op=='item.list':
   schema({'dataset':text},{'status':lambda x:require(x in ('pending','reviewing','complete'))});ds=dataset()
   return [public(i) for _,i in sorted(ds['items'].items()) if 'status' not in d or i['status']==d['status']]
  if op=='report':
   schema({'dataset':text});ds=dataset();r={k:0 for k in ('pending','reviewing','complete','disputed')}
   for i in ds['items'].values():
    r[i['status']]+=1
    if i['status']=='complete' and i['consensus'] is None:r['disputed']+=1
   return r
  raise ValueError('Unknown operation')

if __name__=='__main__':Service.main()
