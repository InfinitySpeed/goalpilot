from goalpilot_runtime import ReplayService, require, fields, text, integer, identifiers, get_record, compare_revision, idempotent

def banner():return 'Local Ops — café'

def nat(x):return integer(x)
def positive(x):return integer(x,minimum=1)

class Service(ReplayService):
 def initial(self):return {'teams':{},'policies':{},'incidents':{},'keys':{}}
 def public(self,r):return {k:r[k] for k in ('id','team','title','status','owner','revision','level','acknowledged','resolved','paused')}
 def elapsed(self,r,now):
  end=r['resolved'] if r['status']=='resolved' else now
  return end-r['start']-r['spent']-(end-r['pause_start'] if r['paused'] else 0)
 def breaches(self,r,now):
  elapsed=self.elapsed(r,now); active=r['status']!='resolved'
  return elapsed,active and r['acknowledged'] is None and elapsed>=r['sla']['response'],active and elapsed>=r['sla']['resolve']
 def handle(self,s,op,d):
  if op=='team.put':
   fields(d,{'id':text,'members':lambda x:identifiers(x,nonempty=True)})
   members=identifiers(d['members'],nonempty=True)
   require(all(r['owner'] is None or r['owner'] in members for r in s['incidents'].values() if r['team']==d['id'] and r['status']!='resolved'),'Assigned owner cannot be removed')
   s['teams'][d['id']]={'id':d['id'],'members':members};return s['teams'][d['id']]
  if op=='policy.put':
   fields(d,{'id':text,'response':positive,'resolve':positive});require(d['resolve']>=d['response'])
   s['policies'][d['id']]=dict(d);return s['policies'][d['id']]
  if op=='incident.open':
   fields(d,{'id':text,'team':text,'policy':text,'now':nat,'title':text,'key':text})
   def create():
    require(d['id'] not in s['incidents'],'Duplicate incident')
    get_record(s['teams'],d['team']);policy=get_record(s['policies'],d['policy'])
    r={'id':d['id'],'team':d['team'],'title':d['title'],'status':'open','owner':None,'revision':1,'level':0,'acknowledged':None,'resolved':None,'paused':False,'start':d['now'],'last':d['now'],'spent':0,'pause_start':None,'sla':dict(policy),'escalations':[]}
    s['incidents'][r['id']]=r;return self.public(r)
   return idempotent(s,d['key'],op,dict(d),create)
  if op=='incident.import':
   fields(d,{'incidents':lambda x:require(isinstance(x,list))})
   for payload in d['incidents']:self.handle(s,'incident.open',payload)
   return {'imported':len(d['incidents'])}
  if op=='incident.list':
   fields(d,{}, {'team':text,'status':lambda x:require(x in ('open','acknowledged','resolved'))})
   return [self.public(r) for _,r in sorted(s['incidents'].items()) if all(r[k]==v for k,v in d.items())]
  if op=='incident.inspect':
   fields(d,{'id':text,'now':nat});r=get_record(s['incidents'],d['id']);require(d['now']>=r['last'])
   elapsed,response,resolve=self.breaches(r,d['now'])
   return dict(self.public(r),elapsed=elapsed,response_breached=response,resolve_breached=resolve)
  require(op in ('incident.assign','incident.ack','incident.pause','incident.resume','incident.resolve','incident.reopen','escalate'),'Unknown operation')
  schema={'id':text,'expected_revision':positive,'now':nat}
  if op=='incident.assign':schema['owner']=text
  fields(d,schema);r=get_record(s['incidents'],d['id']);compare_revision(r,d['expected_revision']);now=d['now'];require(now>=r['last'],'Time moved backwards')
  if op=='incident.reopen':
   require(r['status']=='resolved');require(r['owner'] is None or r['owner'] in s['teams'][r['team']]['members'],'Owner no longer a member')
   r.update(status='open',acknowledged=None,resolved=None,paused=False,start=now,spent=0,pause_start=None,level=0,escalations=[])
  else:
   require(r['status']!='resolved','Incident resolved')
   if op=='incident.assign':
    require(d['owner'] in s['teams'][r['team']]['members']);r['owner']=d['owner']
   elif op=='incident.ack':
    require(r['status']=='open' and r['acknowledged'] is None);r.update(status='acknowledged',acknowledged=now)
   elif op=='incident.pause':
    require(not r['paused']);r.update(paused=True,pause_start=now)
   elif op=='incident.resume':
    require(r['paused']);r['spent']+=now-r['pause_start'];r.update(paused=False,pause_start=None)
   elif op=='incident.resolve':
    require(not r['paused']);r.update(status='resolved',resolved=now)
   else:
    elapsed,response,resolve=self.breaches(r,now);require(response or resolve,'No SLA breach');require(elapsed not in r['escalations'],'Already escalated at elapsed time')
    r['escalations'].append(elapsed);r['level']+=1
  r['last']=now;r['revision']+=1;return self.public(r)

if __name__=='__main__':Service.main()
