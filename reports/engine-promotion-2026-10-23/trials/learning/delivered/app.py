from goalpilot_runtime import ReplayService, require, fields, text, integer, identifiers, sequence, idempotent, get_record, dag

def banner():return 'Local Ops — café'

class Service(ReplayService):
 def initial(self):return {'students':{},'courses':{},'enrollments':{},'keys':{}}
 def handle(self,s,op,d):
  if op=='student.put':
   fields(d,{'id':text,'name':text}); s['students'][d['id']]=dict(d); return dict(d)
  if op=='course.put':
   fields(d,{'id':text,'prerequisites':identifiers,'capacity':integer,'price':integer})
   c={**d,'prerequisites':identifiers(d['prerequisites'])}
   for p in c['prerequisites']:get_record(s['courses'],p)
   require(c['capacity']>=sum(e['course']==c['id'] and e['status']=='enrolled' for e in s['enrollments'].values()))
   s['courses'][c['id']]=c; dag({k:v['prerequisites'] for k,v in s['courses'].items()}); return c
  if op=='enroll':return self.enroll(s,d)
  if op=='enroll.import':
   fields(d,{'requests':sequence(lambda x:fields(x,{'student':text,'course':text,'key':text}))})
   for r in d['requests']:self.enroll(s,r)
   return {'imported':len(d['requests'])}
  if op=='enrollment.get':
   fields(d,{'id':text}); return get_record(s['enrollments'],d['id'])
  if op=='enrollment.list':
   fields(d,{}, {'course':text,'student':text})
   for k in d:get_record(s['courses' if k=='course' else 'students'],d[k])
   return [e for e in s['enrollments'].values() if all(e[k]==v for k,v in d.items())]
  if op=='complete':
   fields(d,{'id':text,'score':lambda v:integer(v,maximum=100)})
   e=get_record(s['enrollments'],d['id']); require(e['status']=='enrolled'); e.update(status='completed',score=d['score']); self.promote(s,e['course']); return e
  if op=='cancel':
   fields(d,{'id':text}); e=get_record(s['enrollments'],d['id'])
   require(e['status'] in ('waiting','enrolled','cancelled'))
   if e['status']!='cancelled':
    e['refund']=e['price'] if e['status']=='enrolled' else 0; e['status']='cancelled'; self.promote(s,e['course'])
   return {'id':e['id'],'status':'cancelled','refund':e['refund']}
  if op=='course.report':
   fields(d,{'id':text}); get_record(s['courses'],d['id']); es=[e for e in s['enrollments'].values() if e['course']==d['id']]
   return {**{k:sum(e['status']==k for e in es) for k in ('enrolled','waiting','completed','cancelled')},'revenue':sum(e['price'] for e in es if e['status'] in ('enrolled','completed')),'waitlist':[e['student'] for e in es if e['status']=='waiting']}
  raise ValueError('Unknown operation')
 def enroll(self,s,d):
  fields(d,{'student':text,'course':text,'key':text})
  def create():
   get_record(s['students'],d['student']); c=get_record(s['courses'],d['course'])
   es=list(s['enrollments'].values())
   passed={e['course'] for e in es if e['student']==d['student'] and e['status']=='completed' and e['score']>=60}
   require(set(c['prerequisites'])<=passed,'Prerequisites not completed')
   require(not any(e['student']==d['student'] and e['course']==d['course'] and e['status']!='cancelled' for e in es),'Already requested')
   status='enrolled' if sum(e['course']==d['course'] and e['status']=='enrolled' for e in es)<c['capacity'] else 'waiting'
   e={'id':self.opaque(),'student':d['student'],'course':d['course'],'status':status,'price':c['price'],'score':None}; s['enrollments'][e['id']]=e; return e
  return idempotent(s,d['key'],'enroll',dict(d),create)
 def promote(self,s,course):
  seats=s['courses'][course]['capacity']-sum(e['course']==course and e['status']=='enrolled' for e in s['enrollments'].values())
  for e in s['enrollments'].values():
   if seats and e['course']==course and e['status']=='waiting':e['status']='enrolled'; seats-=1

if __name__=='__main__':Service.main()
