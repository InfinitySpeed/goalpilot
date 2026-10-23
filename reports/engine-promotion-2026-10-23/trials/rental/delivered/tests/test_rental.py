import unittest
from app import Service
from goalpilot_support import JourneyMixin, rejects


class Rental(JourneyMixin,unittest.TestCase):
 def setUp(self):self.open_service(Service)

 def test_journey(self):
  def flow(c):
   self.assertEqual(c('asset.put',id='é',quantity=3,rate=10),{'id':'é','quantity':3,'rate':10})
   p={'id':'a','asset':'é','quantity':2,'start':10,'end':20,'key':'k'}
   expected={k:v for k,v in p.items() if k!='key'};expected.update(status='confirmed',revision=1,fee=0)
   self.assertEqual(c('booking.create',**p),expected)
   self.assertEqual(c('booking.create',**p),expected)
   rejects(lambda:c('booking.create',**{**p,'quantity':1}))
   rejects(lambda:c('booking.create',**{**p,'id':'b','key':'b'}))
   rejects(lambda:c('asset.put',id='é',quantity=1,rate=99))
   self.assertEqual(c('available',asset='é',start=0,end=30),{'quantity':1})
   self.assertEqual(c('available',asset='é',start=20,end=30),{'quantity':3})
   rejects(lambda:c('booking.pickup',id='a',expected_revision=1,now=9))
   active={**expected,'status':'active','revision':2}
   self.assertEqual(c('booking.pickup',id='a',expected_revision=1,now=10),active)
   c('asset.put',id='é',quantity=3,rate=999)
   rejects(lambda:c('booking.return',id='a',expected_revision=1,now=22,damaged=0))
   returned={**expected,'status':'returned','revision':3,'fee':340}
   self.assertEqual(c('booking.return',id='a',expected_revision=2,now=22,damaged=1),returned)
   rejects(lambda:c('booking.return',id='a',expected_revision=3,now=22,damaged=0))
   self.assertEqual(c('booking.create',**p),expected)
   self.assertEqual(c('booking.get',id='a'),returned)
   self.assertEqual(c('booking.list',asset='é',status='returned'),[returned])
   q={**p,'id':'b','key':'b','quantity':3}
   rejects(lambda:c('booking.import',bookings=[q,{**q,'id':'c','key':'c'}]))
   self.assertEqual(c('booking.list'),[returned])
   self.assertEqual(c('booking.import',bookings=[p,q]),{'imported':2})
   self.assertEqual(c('booking.cancel',id='b',expected_revision=1)['status'],'cancelled')
   self.assertEqual(c('available',asset='é',start=10,end=20),{'quantity':3})
   backup=c('backup');c('asset.put',id='other',quantity=1,rate=1);c('restore',state=backup)
   self.assertEqual(c('asset.list'),[{'id':'é','quantity':3,'rate':999}])
   for bad in (True,1.5,'2',-1):rejects(lambda:c('asset.put',id='bad',quantity=bad,rate=0))
  self.assertJourney(flow)

 def test_restore_and_races(self):
  self.c('asset.put',id='x',quantity=1,rate=2)
  p={'id':'a','asset':'x','quantity':1,'start':0,'end':10,'key':'a'}
  results=self.race(*[('booking.create',p),('booking.create',{**p,'id':'b','key':'b'})])
  self.assertEqual(sum(ok for ok,_ in results),1)
  winner=self.c('booking.list')[0]
  p={**p,'id':winner['id'],'key':winner['id']}
  results=self.race(*[('booking.create',p)]*2)
  self.assertTrue(all(ok for ok,_ in results))
  self.assertEqual(len(self.c('booking.list')),1)
  self.restart();self.assertEqual(self.c('booking.get',id=winner['id']),winner)
  self.assertCorruptions(lambda b:b['state']['bookings'][winner['id']].update(fee=99),lambda b:b['state']['assets']['x'].update(quantity=0),lambda b:b['state']['keys'].clear())
