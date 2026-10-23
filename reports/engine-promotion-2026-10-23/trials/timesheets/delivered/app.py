from goalpilot_runtime import ReplayService, require, fields, text, integer, boolean, choice, sequence, get_record, compare_revision

def banner():return 'Local Ops — café'

class Service(ReplayService):
 def initial(self):return {'projects':{},'workers':{},'entries':{},'locks':{}}
 def handle(self,s,op,d):
  def schema(required,optional=None):fields(d,required,optional)
  def overlap(a,b):return a['start']<b['end'] and b['start']<a['end']
  def unlocked(e):require(not any(overlap(e,l) for l in s['locks'].values()),'Period locked')
  def available(e):require(not any(x['id']!=e['id'] and x['worker']==e['worker'] and overlap(e,x) for x in s['entries'].values()),'Overlapping entries')
  def interval(e):require(e['end']>e['start'],'Invalid interval')
  def report(pid):
   p=get_record(s['projects'],pid); rows=[e for e in s['entries'].values() if e['project']==pid and e['status']=='approved']; minutes=sum(e['end']-e['start'] for e in rows)
   return {'approved':minutes,'remaining':p['budget']-minutes,'amount':sum((e['end']-e['start'])*e['rate'] for e in rows)}
  create={'id':text,'worker':text,'project':text,'start':integer,'end':integer,'note':text}
  if op=='project.put':
   schema({'id':text,'budget':integer,'rate':integer}); approved=report(d['id'])['approved'] if d['id'] in s['projects'] else 0
   require(d['budget']>=approved,'Budget exceeded'); s['projects'][d['id']]=dict(d); return s['projects'][d['id']]
  if op=='worker.put':
   schema({'id':text,'role':choice('worker','manager')}); s['workers'][d['id']]=dict(d); return s['workers'][d['id']]
  if op=='entry.create':
   schema(create); require(d['id'] not in s['entries'],'Duplicate entry'); get_record(s['workers'],d['worker']); p=get_record(s['projects'],d['project'])
   e=dict(d,status='draft',revision=1,rate=p['rate']); interval(e); unlocked(e); available(e); s['entries'][e['id']]=e; return e
  if op=='entry.import':
   schema({'entries':sequence(lambda row:fields(row,create))})
   for row in d['entries']:self.handle(s,'entry.create',row)
   return {'imported':len(d['entries'])}
  if op=='entry.get':schema({'id':text}); return get_record(s['entries'],d['id'])
  if op=='entry.list':
   schema({}, {'worker':text,'project':text,'status':choice('draft','submitted','approved','rejected')})
   return sorted([e for e in s['entries'].values() if all(e[k]==v for k,v in d.items())],key=lambda e:(e['start'],e['id']))
  if op in ('entry.edit','entry.submit','entry.review','entry.delete'):
   spec={'id':text,'expected_revision':integer}
   if op=='entry.edit':spec.update(start=integer,end=integer,note=text)
   if op=='entry.review':spec.update(actor=text,approve=boolean)
   schema(spec); e=get_record(s['entries'],d['id']); compare_revision(e,d['expected_revision']); unlocked(e)
   if op=='entry.edit':
    require(e['status'] in ('draft','rejected'),'Entry not editable'); new=dict(e,start=d['start'],end=d['end'],note=d['note'],status='draft',revision=e['revision']+1)
    interval(new); unlocked(new); available(new); s['entries'][e['id']]=new; return new
   if op=='entry.delete':
    require(e['status'] in ('draft','rejected'),'Entry not deletable'); del s['entries'][e['id']]; return {'deleted':e['id']}
   if op=='entry.submit':require(e['status']=='draft','Entry not draft'); e['status']='submitted'
   else:
    require(e['status']=='submitted','Entry not submitted'); actor=get_record(s['workers'],d['actor']); require(actor['role']=='manager' and d['actor']!=e['worker'],'Separate manager required')
    if d['approve']:require(report(e['project'])['remaining']>=e['end']-e['start'],'Budget exceeded')
    e['status']='approved' if d['approve'] else 'rejected'
   e['revision']+=1; return e
  if op=='period.lock':
   schema({'id':text,'start':integer,'end':integer}); interval(d); require(d['id'] not in s['locks'],'Duplicate lock'); unlocked(d)
   for e in s['entries'].values():
    if overlap(e,d):require(e['status']=='approved' and d['start']<=e['start'] and e['end']<=d['end'],'Unapproved or straddling entry')
   s['locks'][d['id']]=dict(d); return s['locks'][d['id']]
  if op=='invoice.export':
   schema({'lock':text}); l=get_record(s['locks'],d['lock']); rows=[{'entry':e['id'],'worker':e['worker'],'project':e['project'],'minutes':e['end']-e['start'],'amount':(e['end']-e['start'])*e['rate']} for e in sorted(s['entries'].values(),key=lambda e:e['id']) if l['start']<=e['start'] and e['end']<=l['end']]
   return {'items':rows,'total':sum(r['amount'] for r in rows)}
  if op=='project.report':schema({'id':text}); return report(d['id'])
  raise ValueError('Unknown operation')

if __name__=='__main__':Service.main()
