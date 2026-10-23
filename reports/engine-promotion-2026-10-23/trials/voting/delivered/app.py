from goalpilot_runtime import ReplayService, require, text, integer, boolean, fields, sequence, get_record, compare_revision, idempotent

def banner():return 'Local Ops — café'

def ids(v):
 require(isinstance(v,list)); [text(x) for x in v]; return sorted(set(v))
def ranking(v):
 require(isinstance(v,list) and bool(v)); [text(x) for x in v]; require(len(v)==len(set(v))); return v[:]
def positive(v): return integer(v,minimum=1)

class Service(ReplayService):
 def initial(self): return {'members':{},'polls':{},'keys':{}}
 def handle(self,s,op,d):
  if op=='member.put':
   fields(d,{'id':text,'active':boolean}); s['members'][d['id']]={'id':d['id'],'active':d['active']}; return s['members'][d['id']]
  if op=='poll.create':
   fields(d,{'id':text,'candidates':ids,'quorum':positive}); candidates=ids(d['candidates']); require(len(candidates)>=2); require(d['id'] not in s['polls'])
   p={'id':d['id'],'candidates':candidates,'quorum':d['quorum'],'status':'draft','revision':1,'eligible':[],'ballots':{},'delegations':{}}; s['polls'][d['id']]=p; return p
  if op=='poll.list':
   fields(d,{}); return [s['polls'][i] for i in sorted(s['polls'])]
  if op in ('poll.get','poll.open','poll.close'):
   fields(d,{'id':text},{} if op=='poll.get' else {'expected_revision':positive}); p=get_record(s['polls'],d['id'])
   if op=='poll.get': return p
   require('expected_revision' in d); compare_revision(p,d['expected_revision']); require(p['status']==('draft' if op=='poll.open' else 'open'))
   if op=='poll.open': p['eligible']=sorted(i for i,m in s['members'].items() if m['active'])
   p['status']='open' if op=='poll.open' else 'closed'; p['revision']+=1; return p
  if op in ('delegate','undelegate'):
   fields(d,{'poll':text,'member':text}, {'to':text} if op=='delegate' else {}); p=get_record(s['polls'],d['poll']); m=d['member']; require(p['status']=='open' and m in p['eligible'])
   if op=='undelegate':
    require(m in p['delegations']); del p['delegations'][m]
   else:
    require('to' in d); to=d['to']; require(to in p['eligible'] and to!=m and m not in p['ballots']); seen={m}; node=to
    while True:
     require(node not in seen,'Delegation cycle'); seen.add(node)
     if node not in p['delegations']: break
     node=p['delegations'][node]
    p['delegations'][m]=to
   return p
  if op=='vote':
   fields(d,{'poll':text,'member':text,'ranking':ranking,'key':text}); request={k:d[k] for k in ('poll','member','ranking')}
   def cast():
    p=get_record(s['polls'],d['poll']); m=d['member']; require(p['status']=='open' and m in p['eligible']); require(m not in p['delegations'] and m not in p['ballots']); require(set(d['ranking'])<=set(p['candidates'])); p['ballots'][m]=d['ranking'][:]; return request
   return idempotent(s,d['key'],op,request,cast)
  if op=='vote.import':
   fields(d,{'votes':sequence(lambda v:fields(v,{'poll':text,'member':text,'ranking':ranking,'key':text}))})
   for v in d['votes']: self.handle(s,'vote',v)
   return {'imported':len(d['votes'])}
  if op=='tally':
   fields(d,{'poll':text}); p=get_record(s['polls'],d['poll']); require(p['status']=='closed'); represented=[]
   for m in p['eligible']:
    while m in p['delegations']: m=p['delegations'][m]
    if m in p['ballots']: represented.append(p['ballots'][m])
   n=len(represented); result={'quorum_met':n>=p['quorum'],'participating':n,'winner':None,'rounds':[]}
   if not result['quorum_met']: return result
   active=p['candidates'][:]
   while active:
    counts=dict.fromkeys(active,0); exhausted=0
    for ballot in represented:
     candidate=next((c for c in ballot if c in counts),None)
     if candidate is None: exhausted+=1
     else: counts[candidate]+=1
    total=n-exhausted; winner=next((c for c in active if counts[c]*2>total),None) if total else None
    eliminated=None
    if total and winner is None and len(active)>1: eliminated=max(c for c in active if counts[c]==min(counts.values()))
    result['rounds'].append({'counts':counts,'exhausted':exhausted,'eliminated':eliminated})
    if winner is not None: result['winner']=winner; break
    if eliminated is None: break
    active.remove(eliminated)
   return result
  raise ValueError('Unknown operation')

if __name__=='__main__': Service.main()
