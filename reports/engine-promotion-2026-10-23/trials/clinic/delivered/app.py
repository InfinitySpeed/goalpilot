from goalpilot_runtime import ReplayService, require, fields, text, integer, boolean, sequence, idempotent, get_record, compare_revision


def banner():return 'Local Ops — café'


class Service(ReplayService):
 def initial(self):return dict(practitioners={},patients={},appointments={},wait={},keys={})
 def handle(self,s,op,d):
  create=dict(id=text,patient=text,practitioner=text,start=integer,end=integer,skill=text,fee=integer,key=text)
  def interval(v):require(v['end']>v['start'],'Invalid interval')
  def available(a,ignore=None):
   for other in s['appointments'].values():
    if other['id']!=ignore and other['status']!='cancelled' and (other['patient']==a['patient'] or other['practitioner']==a['practitioner']):
     require(a['end']<=other['start'] or other['end']<=a['start'],'Overlapping appointment')
  def book(v):
   fields(v,create);interval(v)
   def apply():
    require(v['id'] not in s['appointments'],'Duplicate appointment')
    require(get_record(s['patients'],v['patient'])['consent'],'Consent required')
    require(v['skill'] in get_record(s['practitioners'],v['practitioner'])['skills'],'Skill required')
    a={k:x for k,x in v.items() if k!='key'}
    a.update(status='confirmed',revision=1,charged=0)
    available(a);s['appointments'][a['id']]=a
    return a
   return idempotent(s,v['key'],'appointment.create',v,apply)
  if op=='practitioner.put':
   fields(d,dict(id=text,skills=sequence(text)))
   skills=sorted(set(d['skills']))
   require(all(a['skill'] in skills for a in s['appointments'].values() if a['practitioner']==d['id'] and a['status']!='cancelled'),'Skill in use')
   r=dict(id=d['id'],skills=skills);s['practitioners'][d['id']]=r;return r
  if op=='patient.put':
   fields(d,dict(id=text,consent=boolean));s['patients'][d['id']]=dict(d);return d
  if op=='appointment.create':return book(d)
  if op=='appointment.import':
   fields(d,dict(appointments=sequence(lambda v:fields(v,create))))
   for v in d['appointments']:book(v)
   return dict(imported=len(d['appointments']))
  if op in ('appointment.move','appointment.cancel','appointment.finish'):
   spec=dict(id=text,expected_revision=integer)
   if op.endswith('move'):spec.update(start=integer,end=integer)
   if op.endswith('finish'):spec.update(attended=boolean)
   fields(d,spec);a=get_record(s['appointments'],d['id']);compare_revision(a,d['expected_revision'])
   require(a['status']=='confirmed','Appointment is completed or cancelled')
   if op.endswith('move'):
    interval(d);candidate=dict(a,start=d['start'],end=d['end']);available(candidate,a['id']);a.update(start=d['start'],end=d['end'])
   elif op.endswith('cancel'):a['status']='cancelled'
   else:
    a['status']='attended' if d['attended'] else 'missed';a['charged']=a['fee'] if d['attended'] else a['fee']//2
   a['revision']+=1;return a
  if op=='appointment.get':
   fields(d,dict(id=text));return get_record(s['appointments'],d['id'])
  if op=='appointment.list':
   fields(d,{},dict(patient=text,practitioner=text,status=text))
   if 'status' in d:require(d['status'] in ('confirmed','cancelled','attended','missed'),'Invalid status')
   return sorted((a for a in s['appointments'].values() if all(a[k]==v for k,v in d.items())),key=lambda a:(a['start'],a['id']))
  if op=='invoice':
   fields(d,dict(patient=text));get_record(s['patients'],d['patient'])
   rows=[a for a in s['appointments'].values() if a['patient']==d['patient']]
   return dict(charged=sum(a['charged'] for a in rows),attended=sum(a['status']=='attended' for a in rows),missed=sum(a['status']=='missed' for a in rows))
  if op=='wait.add':
   fields(d,dict(id=text,patient=text,skill=text));require(d['id'] not in s['wait'],'Duplicate wait ID')
   require(get_record(s['patients'],d['patient'])['consent'],'Consent required')
   require(not any(w['patient']==d['patient'] and w['skill']==d['skill'] for w in s['wait'].values()),'Duplicate wait request')
   s['wait'][d['id']]=dict(d);return d
  if op=='wait.list':
   fields(d,dict(skill=text));return [w for w in s['wait'].values() if w['skill']==d['skill']]
  if op=='wait.remove':
   fields(d,dict(id=text));r=get_record(s['wait'],d['id']);del s['wait'][d['id']];return r
  raise ValueError('Unknown operation')


if __name__=='__main__':Service.main()
