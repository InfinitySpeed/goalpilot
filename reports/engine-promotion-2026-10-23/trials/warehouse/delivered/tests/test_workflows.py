import unittest
from app import Service
from goalpilot_support import JourneyMixin, rejects


class Workflows(JourneyMixin, unittest.TestCase):
    def setUp(self): self.open_service(Service)

    def test_journey(self):
        def flow(c):
            self.assertEqual(c('product.put', id='p', name='café'), {'id':'p','name':'café'})
            a = dict(id='a', product='p', quantity=4, expires=5, key='a')
            first = c('lot.receive', **a)
            self.assertEqual(first, dict(id='a',product='p',on_hand=4,reserved=0,expires=5))
            self.assertEqual(c('lot.import', lots=[dict(a,id='b',key='b',expires=10)]), {'imported':1})
            draft = c('order.create', id='o', lines=[dict(product='p',quantity=2),dict(product='p',quantity=4)])
            self.assertEqual(draft, dict(id='o',status='draft',lines=[dict(product='p',quantity=6)],allocations=[],shipped=[],returned=[]))
            confirmed = c('order.allocate', id='o', now=0)
            self.assertEqual(confirmed['allocations'], [dict(lot='a',quantity=4),dict(lot='b',quantity=2)])
            self.assertEqual(c('order.allocate',id='o',now=99), confirmed)
            part = c('order.ship', id='o', lines=[dict(lot='a',quantity=1),dict(lot='a',quantity=1)], key='ship')
            self.assertEqual(part['status'],'partial')
            c('order.return',id='o',lines=[dict(lot='a',quantity=1)],key='return')
            self.assertEqual(c('order.ship',id='o',lines=[dict(lot='a',quantity=2)],key='ship'),part)
            self.assertEqual(c('lot.receive',**a),first)
            rejects(lambda:c('order.return',id='o',lines=[dict(lot='a',quantity=2)],key='bad'))
            cancelled=c('order.cancel',id='o')
            self.assertEqual(cancelled['status'],'cancelled')
            self.assertEqual(c('order.cancel',id='o'),cancelled)
            self.assertEqual(c('stock.report',product='p',now=5),dict(on_hand=7,reserved=0,available=4,expired=3))
            self.assertEqual([l['id'] for l in c('lot.list',now=5)],['b'])
            c('order.create',id='full',lines=[dict(product='p',quantity=4)])
            c('order.allocate',id='full',now=5)
            self.assertEqual(c('order.ship',id='full',lines=[dict(lot='b',quantity=4)],key='full')['status'],'shipped')
            rejects(lambda:c('order.cancel',id='full'))
            c('order.create',id='short',lines=[dict(product='p',quantity=1)])
            rejects(lambda:c('order.allocate',id='short',now=5))
            rejects(lambda:c('lot.receive',**dict(a,id='bad',key='bad',quantity=True)))
            rejects(lambda:c('lot.import',lots=[dict(a,id='new',key='new'),a | {'quantity':8}]))
            snapshot=c('backup')
            c('product.put',id='p',name='changed')
            c('restore',state=snapshot)
            self.assertEqual(c('backup'),snapshot)
        self.assertJourney(flow)

    def test_restore_and_races(self):
        self.c('product.put',id='p',name='P')
        payload=dict(id='l',product='p',quantity=3,expires=10,key='r')
        results=self.race(*[('lot.receive',payload)]*2)
        self.assertTrue(all(ok for ok,_ in results))
        self.assertEqual(results[0][1],results[1][1])
        for oid in ('a','b'): self.c('order.create',id=oid,lines=[dict(product='p',quantity=2)])
        results=self.race(*[('order.allocate',dict(id=oid,now=0)) for oid in ('a','b')])
        self.assertEqual(sum(ok for ok,_ in results),1)
        self.assertEqual(self.c('stock.report',product='p',now=0)['reserved'],2)
        self.assertCorruptions(lambda b:b['state']['lots']['l'].__setitem__('reserved',0), lambda b:b['state']['orders']['a'].__setitem__('status','shipped'))
        self.restart()
        self.assertEqual(self.c('stock.report',product='p',now=0)['on_hand'],3)
