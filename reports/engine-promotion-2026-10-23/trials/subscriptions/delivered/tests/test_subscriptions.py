import unittest
from app import Service
from goalpilot_support import JourneyMixin, rejects

class Billing(JourneyMixin,unittest.TestCase):
 def setUp(self):self.open_service(Service)
 def test_journey(self):
  def flow(c):
   c('plan.put',id='basic',price=100,period=10);c('plan.put',id='plus',price=201,period=10)
   a=c('subscriber.create',id='é',plan='basic',start=0)
   self.assertEqual(a,dict(id='é',plan='basic',status='active',start=0,period_end=10,price=100,period=10,cancel_at_end=False,balance=0,revision=1))
   rejects(lambda:c('bill',id='é',now=9,key='early'))
   r=c('subscriber.change',id='é',plan='plus',now=5,expected_revision=1)
   self.assertEqual(r['adjustment'],50);self.assertEqual(r['subscriber']['balance'],50)
   rejects(lambda:c('subscriber.change',id='é',plan='basic',now=6,expected_revision=2))
   v=c('invoice.list',subscriber='é')[0]
   pay=dict(id=v['id'],amount=50,key='pay')
   self.assertEqual(c('invoice.pay',**pay)['paid'],50);self.assertEqual(c('invoice.pay',**pay)['paid'],50)
   r=c('subscriber.change',id='é',plan='basic',now=6,expected_revision=2)
   self.assertEqual(r['adjustment'],-41);self.assertEqual(r['subscriber']['balance'],0)
   r=c('bill',id='é',now=30,key='renew')
   self.assertEqual([v['due'] for v in r['invoices']],[10,20,30]);self.assertEqual(r['subscriber']['period_end'],40)
   self.assertEqual(c('bill',id='é',now=30,key='renew'),r)
   rejects(lambda:c('bill',id='é',now=31,key='renew'))
   rejects(lambda:c('bill',id='é',now=30,key='different'))
   payments=[dict(id=v['id'],amount=100,key='p'+str(i)) for i,v in enumerate(r['invoices'])]
   rejects(lambda:c('invoice.import_payments',payments=payments+[dict(id='missing',amount=1,key='bad')]))
   self.assertEqual(c('subscriber.get',id='é')['balance'],300)
   self.assertEqual(c('invoice.import_payments',payments=payments),{'imported':3})
   c('subscriber.cancel',id='é',expected_revision=3)
   r=c('bill',id='é',now=100,key='cancel')
   self.assertEqual(r['invoices'],[]);self.assertEqual(r['subscriber']['status'],'cancelled');self.assertEqual(r['subscriber']['period_end'],40)
   self.assertEqual(c('report'),dict(subscribers=1,active=0,past_due=0,cancelled=1,invoiced=350,collected=350,outstanding=0))
   backup=c('backup');c('plan.put',id='other',price=1,period=1);c('restore',state=backup)
   self.assertEqual(c('backup'),backup)
   rejects(lambda:c('plan.put',id='bad',price=True,period=1))
   rejects(lambda:c('subscriber.get',id='missing'))
  self.assertJourney(flow)
 def test_restore_and_race(self):
  self.c('plan.put',id='p',price=10,period=1);self.c('subscriber.create',id='s',plan='p',start=0)
  results=self.race(*[('bill',dict(id='s',now=2,key='same'))]*2)
  self.assertTrue(all(ok for ok,_ in results));self.assertEqual(results[0][1],results[1][1])
  self.assertEqual(self.c('report')['invoiced'],20)
  self.assertCorruptions(lambda b:b['state']['subscribers']['s'].update(balance=0),lambda b:b['state']['invoices'].clear())
  self.restart();self.assertEqual(self.c('subscriber.get',id='s')['balance'],20)
