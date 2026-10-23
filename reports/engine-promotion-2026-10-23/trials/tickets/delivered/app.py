from goalpilot_runtime import ReplayService, require, fields, text, integer, identifiers, sequence, idempotent, get_record


def banner():return 'Local Ops — café'


class Service(ReplayService):
 def initial(self):return {'events':{},'holds':{},'orders':{},'keys':{}}

 def handle(self,s,op,d):
  nat=integer
  def ids(v):return identifiers(v,nonempty=True)
  def positive(v):return integer(v,minimum=1)
  hold_fields={'id':text,'event':text,'seats':ids,'now':nat,'ttl':positive}
  def free(event,now):
   occupied=set()
   for h in s['holds'].values():
    if h['event']==event and h['status']=='held' and now<h['expires']:occupied.update(h['seats'])
   for o in s['orders'].values():
    if o['event']==event and o['status']=='paid':occupied.update(o['seats'])
   return sorted(set(s['events'][event]['seats'])-occupied)
  def hold(row):
   fields(row,hold_fields)
   hid=row['id']; eid=row['event']; seats=ids(row['seats'])
   require(hid not in s['holds'],'Duplicate hold')
   e=get_record(s['events'],eid)
   require(set(seats)<=set(free(eid,row['now'])),'Seats unavailable')
   h={'id':hid,'event':eid,'seats':seats,'expires':row['now']+row['ttl'],'status':'held','price':len(seats)*e['price']}
   s['holds'][hid]=h
   return h
  if op=='event.create':
   fields(d,{'id':text,'seats':ids,'price':nat})
   require(d['id'] not in s['events'],'Duplicate event')
   e={'id':d['id'],'seats':ids(d['seats']),'price':d['price']};s['events'][e['id']]=e
   return e
  if op=='event.get':
   fields(d,{'id':text,'now':nat});e=get_record(s['events'],d['id'])
   return dict(e,available=free(e['id'],d['now']))
  if op=='hold.create':return hold(d)
  if op=='hold.import':
   fields(d,{'holds':sequence(lambda x:fields(x,hold_fields))})
   for row in d['holds']:hold(row)
   return {'imported':len(d['holds'])}
  if op=='hold.cancel':
   fields(d,{'id':text});h=get_record(s['holds'],d['id'])
   require(h['status'] in ('held','cancelled'),'Hold purchased');h['status']='cancelled';return h
  if op=='purchase':
   fields(d,{'hold':text,'now':nat,'key':text})
   def buy():
    h=get_record(s['holds'],d['hold'])
    require(h['status']=='held' and d['now']<h['expires'],'Hold unavailable')
    # A later request may have sold a seat after this hold expired.
    require(all(not(set(h['seats'])&set(o['seats'])) for o in s['orders'].values() if o['event']==h['event'] and o['status']=='paid'),'Seats sold')
    oid=self.opaque();o={'id':oid,'event':h['event'],'seats':list(h['seats']),'total':h['price'],'status':'paid','used':[]}
    s['orders'][oid]=o;h['status']='purchased';return o
   return idempotent(s,d['key'],op,{'hold':d['hold'],'now':d['now']},buy)
  if op in ('order.get','order.refund'):
   fields(d,{'id':text});o=get_record(s['orders'],d['id'])
   if op=='order.refund':
    require(not o['used'],'Already admitted');o['status']='refunded'
   return o
  if op=='checkin':
   fields(d,{'order':text,'seat':text});o=get_record(s['orders'],d['order'])
   require(o['status']=='paid' and d['seat'] in o['seats'] and d['seat'] not in o['used'],'Admission rejected')
   o['used']=sorted(o['used']+[d['seat']]);return {'order':o['id'],'seat':d['seat'],'admitted':True}
  if op=='sales.report':
   fields(d,{'event':text});get_record(s['events'],d['event'])
   orders=[o for o in s['orders'].values() if o['event']==d['event']]
   return {'paid':sum(o['total'] for o in orders if o['status']=='paid'),'refunded':sum(o['total'] for o in orders if o['status']=='refunded'),'admitted':sum(len(o['used']) for o in orders if o['status']=='paid')}
  raise ValueError('Unknown operation')


if __name__=='__main__':Service.main()
