import unittest
from app import Service
from goalpilot_support import JourneyMixin, rejects


class Tickets(JourneyMixin,unittest.TestCase):
 def setUp(self):self.open_service(Service)
 def test_journey(self):
  def flow(c):
   self.assertEqual(c('event.create',id='é',seats=['B','A','A'],price=125),{'id':'é','seats':['A','B'],'price':125})
   h=c('hold.create',id='h',event='é',seats=['A'],now=0,ttl=5)
   self.assertEqual(h,{'id':'h','event':'é','seats':['A'],'expires':5,'status':'held','price':125})
   rejects(lambda:c('hold.create',id='bad',event='é',seats=['A','B'],now=1,ttl=2))
   self.assertEqual(c('event.get',id='é',now=5)['available'],['A','B'])
   rejects(lambda:c('purchase',hold='h',now=5,key='expired'))
   c('hold.create',id='h2',event='é',seats=['A'],now=5,ttl=5)
   o=c('purchase',hold='h2',now=6,key='k')
   self.assertEqual(o,dict(id=o['id'],event='é',seats=['A'],total=125,status='paid',used=[]))
   self.assertEqual(c('order.refund',id=o['id'])['status'],'refunded')
   self.assertEqual(c('order.refund',id=o['id'])['total'],125)
   self.assertEqual(c('purchase',hold='h2',now=6,key='k'),o)
   rejects(lambda:c('purchase',hold='h2',now=7,key='k'))
   rejects(lambda:c('checkin',order=o['id'],seat='A'))
   c('hold.import',holds=[dict(id='h3',event='é',seats=['A'],now=10,ttl=5),dict(id='h4',event='é',seats=['B'],now=10,ttl=5)])
   paid=c('purchase',hold='h3',now=11,key='k2')
   self.assertEqual(c('checkin',order=paid['id'],seat='A'),{'order':paid['id'],'seat':'A','admitted':True})
   rejects(lambda:c('checkin',order=paid['id'],seat='A'))
   rejects(lambda:c('order.refund',id=paid['id']))
   self.assertEqual(c('order.get',id=paid['id'])['used'],['A'])
   self.assertEqual(c('sales.report',event='é'),{'paid':125,'refunded':125,'admitted':1})
   c('hold.cancel',id='h4');self.assertEqual(c('hold.cancel',id='h4')['status'],'cancelled')
   for data in [dict(id='x',seats=['X'],price=True),dict(id='',seats=['X'],price=1)]:rejects(lambda:c('event.create',**data))
   snapshot=c('backup');c('event.create',id='temporary',seats=['Z'],price=0);c('restore',state=snapshot)
   rejects(lambda:c('event.get',id='temporary',now=0))
  self.assertJourney(flow)
 def test_atomic_restore_and_race(self):
  self.c('event.create',id='e',seats=['A','B'],price=10)
  self.assertRejects('hold.import',holds=[dict(id='a',event='e',seats=['A'],now=0,ttl=2),dict(id='b',event='e',seats=['A'],now=0,ttl=2)])
  self.assertEqual(self.c('event.get',id='e',now=0)['available'],['A','B'])
  results=self.race(*[('hold.create',dict(id=str(i),event='e',seats=['A'],now=0,ttl=3)) for i in range(2)])
  self.assertEqual(sum(ok for ok,_ in results),1)
  self.restart()
  self.assertEqual(self.c('event.get',id='e',now=0)['available'],['B'])
  self.assertCorruptions(lambda b:b['state']['events']['e'].update(price=99))
