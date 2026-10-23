from copy import deepcopy
from goalpilot_runtime import ReplayService, require, fields, text, integer, choice, get_record, compare_revision


def banner():return 'Local Ops — café'


class Service(ReplayService):
 def initial(self):return {'assets':{},'bookings':{},'keys':{}}

 def free(self,s,asset,start,end):
  events={start:0,end:0}
  for b in s['bookings'].values():
   if b['asset']==asset and b['status'] in ('confirmed','active') and b['start']<end and start<b['end']:
    a,z=max(start,b['start']),min(end,b['end'])
    events[a]=events.get(a,0)+b['quantity'];events[z]=events.get(z,0)-b['quantity']
  used=peak=0
  for t in sorted(events):
   used+=events[t];peak=max(peak,used)
  return s['assets'][asset]['quantity']-peak

 def public(self,b):return {k:v for k,v in b.items() if k!='rate'}

 def create(self,s,d):
  fields(d,{'id':text,'asset':text,'quantity':lambda x:integer(x,minimum=1),'start':integer,'end':integer,'key':text})
  require(d['end']>d['start'],'Invalid interval')
  payload={k:d[k] for k in ('id','asset','quantity','start','end')}
  if d['key'] in s['keys']:
   old=s['keys'][d['key']];require(old['request']==payload,'Key conflict');return deepcopy(old['result'])
  require(d['id'] not in s['bookings'],'Duplicate booking')
  a=get_record(s['assets'],d['asset'])
  require(self.free(s,d['asset'],d['start'],d['end'])>=d['quantity'],'Insufficient stock')
  b={**payload,'status':'confirmed','revision':1,'fee':0,'rate':a['rate']}
  s['bookings'][d['id']]=b
  result=self.public(b);s['keys'][d['key']]={'request':payload,'result':deepcopy(result)}
  return result

 def handle(self,s,op,d):
  if op=='asset.put':
   fields(d,{'id':text,'quantity':integer,'rate':integer})
   if d['id'] in s['assets']:
    old=s['assets'][d['id']]['quantity'];peak=old-self.free(s,d['id'],0,max([b['end'] for b in s['bookings'].values()]+[1]))
    require(d['quantity']>=peak,'Stock below reservations')
   s['assets'][d['id']]=dict(d);return dict(d)
  if op=='asset.list':
   fields(d,{});return [s['assets'][k] for k in sorted(s['assets'])]
  if op=='booking.create':return self.create(s,d)
  if op=='booking.import':
   fields(d,{'bookings':lambda x:require(isinstance(x,list),'Expected list')})
   for b in d['bookings']:self.create(s,b)
   return {'imported':len(d['bookings'])}
  if op=='available':
   fields(d,{'asset':text,'start':integer,'end':integer});require(d['end']>d['start'],'Invalid interval');get_record(s['assets'],d['asset'])
   return {'quantity':self.free(s,d['asset'],d['start'],d['end'])}
  if op=='booking.list':
   fields(d,{}, {'asset':text,'status':choice('confirmed','active','returned','cancelled')})
   if 'asset' in d:get_record(s['assets'],d['asset'])
   return [self.public(b) for _,b in sorted(s['bookings'].items()) if all(b[k]==v for k,v in d.items())]
  if op=='booking.get':
   fields(d,{'id':text});return self.public(get_record(s['bookings'],d['id']))
  if op in ('booking.pickup','booking.return','booking.cancel'):
   spec={'id':text,'expected_revision':lambda x:integer(x,minimum=1)}
   if op!='booking.cancel':spec['now']=integer
   if op=='booking.return':spec['damaged']=integer
   fields(d,spec);b=get_record(s['bookings'],d['id']);compare_revision(b,d['expected_revision'])
   if op=='booking.return':
    require(b['status']=='active' and d['now']>=b['start'] and d['damaged']<=b['quantity'],'Invalid return')
    b['fee']=b['quantity']*(b['end']-b['start']+max(0,d['now']-b['end']))*b['rate']+d['damaged']*100
    b['status']='returned'
   else:
    require(b['status']=='confirmed','Not confirmed')
    if op=='booking.pickup':require(b['start']<=d['now']<b['end'],'Outside pickup interval')
    b['status']='active' if op=='booking.pickup' else 'cancelled'
   b['revision']+=1;return self.public(b)
  raise ValueError('Unknown operation')


if __name__=='__main__':Service.main()
