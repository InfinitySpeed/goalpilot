import unittest
from app import Service
from goalpilot_support import JourneyMixin,rejects

class Manufacturing(JourneyMixin,unittest.TestCase):
 def setUp(self):self.open_service(Service)
 def test_journey(self):
  def flow(c):
   for p,cost in [('a',3),('b',5),('p',99),('top',0)]:c('part.put',id=p,name=p,cost=cost)
   b=c('bom.put',product='p',components=[{'part':'b','quantity':1},{'part':'a','quantity':1},{'part':'a','quantity':1}]);self.assertEqual(b['revision'],1)
   c('bom.put',product='top',components=[{'part':'p','quantity':1}])
   rejects(lambda:c('bom.put',product='a',components=[{'part':'top','quantity':1}]))
   self.assertEqual(c('receive',part='a',quantity=10,key='a'),{'on_hand':10})
   c('receive',part='b',quantity=5,key='b');self.assertEqual(c('receive',part='a',quantity=10,key='a'),{'on_hand':10})
   rejects(lambda:c('receive',part='a',quantity=11,key='a'))
   rejects(lambda:c('receive.import',receipts=[{'part':'a','quantity':9,'key':'new'},{'part':'missing','quantity':1,'key':'bad'}]))
   self.assertEqual(c('stock',part='a')['on_hand'],10)
   w=c('work.create',id='w',product='p',quantity=4);self.assertEqual(w,{'id':'w','product':'p','quantity':4,'produced':0,'scrapped':0,'status':'draft','reserved':[],'cost':0})
   c('part.put',id='a',name='edited',cost=100)
   c('bom.put',product='p',components=[{'part':'a','quantity':1}])
   r=c('work.reserve',id='w');self.assertEqual(r['reserved'],[{'part':'a','quantity':8},{'part':'b','quantity':4}]);self.assertEqual(c('work.reserve',id='w'),r)
   c('work.create',id='blocked',product='p',quantity=3);rejects(lambda:c('work.reserve',id='blocked'))
   r=c('work.finish',id='w',good=1,scrap=1,key='f');self.assertEqual((r['cost'],r['status']),(22,'partial'))
   self.assertEqual(c('work.finish',id='w',good=1,scrap=1,key='f'),r)
   self.assertEqual(c('stock',part='a'),{'on_hand':6,'reserved':4,'available':2})
   snapshot=c('backup');c('work.cancel',id='w');self.assertEqual(c('stock',part='a')['reserved'],0)
   c('restore',state=snapshot);r=c('work.finish',id='w',good=2,scrap=0,key='end');self.assertEqual((r['cost'],r['produced'],r['scrapped'],r['status']),(44,3,1,'complete'))
   rejects(lambda:c('work.cancel',id='w'));self.assertEqual(c('stock',part='p')['on_hand'],3)
   c('work.create',id='nested',product='top',quantity=2);c('work.reserve',id='nested');c('work.finish',id='nested',good=1,scrap=1,key='nested');self.assertEqual(c('stock',part='p')['on_hand'],1)
   c('work.cancel',id='blocked');self.assertEqual(c('work.cancel',id='blocked')['status'],'cancelled')
   self.assertEqual(len(c('work.list',status='complete')),2)
   rejects(lambda:c('receive',part='a',quantity=True,key='bool'))
  self.assertJourney(flow)
 def test_restore_and_race(self):
  self.c('part.put',id='a',name='a',cost=2);self.c('part.put',id='p',name='p',cost=0)
  self.c('bom.put',product='p',components=[{'part':'a','quantity':1}]);self.c('receive',part='a',quantity=1,key='r')
  for i in ('x','y'):self.c('work.create',id=i,product='p',quantity=1)
  results=self.race(*[('work.reserve',{'id':i}) for i in ('x','y')]);self.assertEqual(sum(ok for ok,_ in results),1)
  self.assertCorruptions(lambda b:b['state']['parts']['a'].__setitem__('on_hand',999))
