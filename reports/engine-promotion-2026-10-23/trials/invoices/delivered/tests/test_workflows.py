import unittest
from app import Service
from goalpilot_support import JourneyMixin, rejects

class Workflows(JourneyMixin,unittest.TestCase):
 def setUp(self):self.open_service(Service)
 def test_journey(self):
  def flow(c):
   self.assertEqual(c('customer.put',id='c',name='café'),{'id':'c','name':'café'})
   self.assertEqual(c('customer.list'),[{'id':'c','name':'café'}])
   args=dict(id='i',customer='c',lines=[dict(description='été',quantity=3,unit_cents=101)],tax_bps=5000)
   r=c('invoice.create',**args)
   self.assertEqual(r,dict(id='i',customer='c',lines=args['lines'],status='draft',subtotal=303,tax=152,total=455,paid=0,credited=0,balance=455,revision=1))
   rejects(lambda:c('invoice.pay',id='i',amount=1,key='early'))
   rejects(lambda:c('invoice.issue',id='i',expected_revision=2))
   self.assertEqual(c('invoice.issue',id='i',expected_revision=1)['revision'],2)
   p=c('invoice.pay',id='i',amount=100,key='p')
   self.assertEqual((p['status'],p['balance'],p['revision']),('partial',355,3))
   self.assertEqual(c('invoice.pay',id='i',amount=100,key='p'),p)
   rejects(lambda:c('invoice.credit',id='i',amount=100,key='p'))
   rejects(lambda:c('payment.import',payments=[dict(id='i',amount=100,key='batch'),dict(id='i',amount=400,key='bad')]))
   self.assertEqual(c('invoice.get',id='i'),p)
   self.assertEqual(c('payment.import',payments=[dict(id='i',amount=100,key='batch')]),{'imported':1})
   r=c('invoice.credit',id='i',amount=255,key='credit')
   self.assertEqual((r['paid'],r['credited'],r['balance'],r['status']),(200,255,0,'paid'))
   self.assertEqual(c('statement',customer='c'),dict(invoiced=455,paid=200,credited=255,due=0))
   backup=c('backup'); c('customer.put',id='extra',name='extra'); c('restore',state=backup)
   self.assertEqual(c('customer.list'),[{'id':'c','name':'café'}])
   self.assertEqual(c('invoice.pay',id='i',amount=100,key='p'),p)
   self.assertEqual(c('invoice.list',customer='c',status='paid'),[r])
   for ident in ('v','a'):
    c('invoice.create',**dict(args,id=ident)); c('invoice.issue',id=ident,expected_revision=1)
   self.assertEqual(c('invoice.void',id='v',expected_revision=2)['balance'],0)
   self.assertEqual(c('invoice.credit',id='a',amount=455,key='all')['status'],'credited')
   rejects(lambda:c('invoice.pay',id='v',amount=1,key='void'))
   rejects(lambda:c('invoice.create',**dict(args,id='bad',tax_bps=True)))
  self.assertJourney(flow)
 def test_restore_and_race(self):
  self.c('customer.put',id='c',name='C')
  self.c('invoice.create',id='i',customer='c',lines=[dict(description='x',quantity=1,unit_cents=100)],tax_bps=0)
  self.c('invoice.issue',id='i',expected_revision=1)
  results=self.race(*[('invoice.pay',dict(id='i',amount=100,key='same'))]*2)
  self.assertEqual(sum(ok for ok,_ in results),2)
  self.restart(); self.assertEqual(self.c('invoice.get',id='i')['paid'],100)
  self.assertCorruptions(lambda b:b.clear())
