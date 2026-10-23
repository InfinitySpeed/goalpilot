import unittest
from app import Service
from goalpilot_support import JourneyMixin, rejects


class Procurement(JourneyMixin,unittest.TestCase):
    def setUp(self): self.open_service(Service)

    def test_journey(self):
        def flow(c):
            self.assertEqual(c('department.put',id='café',budget=100),{'id':'café','budget':100})
            for id,role in [('r','requester'),('a','approver'),('b','approver')]:
                self.assertEqual(c('member.put',id=id,department='café',role=role),dict(id=id,department='café',role=role))
            payload=dict(id='p',creator='r',amount=80,approvals=2)
            r=c('request.create',**payload)
            self.assertEqual(r,dict(payload,department='café',approved=[],status='pending',revision=1,refunded=0))
            rejects(lambda:c('request.approve',id='p',actor='r',expected_revision=1))
            r=c('request.approve',id='p',actor='a',expected_revision=1)
            self.assertEqual((r['approved'],r['revision'],r['status']),(['a'],2,'pending'))
            rejects(lambda:c('member.put',id='a',department='café',role='requester'))
            rejects(lambda:c('request.approve',id='p',actor='b',expected_revision=1))
            r=c('request.approve',id='p',actor='b',expected_revision=2)
            self.assertEqual((r['approved'],r['revision'],r['status']),(['a','b'],3,'approved'))
            self.assertEqual(c('department.report',id='café'),dict(budget=100,committed=80,spent=0,available=20))
            rejects(lambda:c('department.put',id='café',budget=79))
            spent=c('request.spend',id='p',key='s')
            self.assertEqual((spent['status'],spent['revision']),('spent',4))
            refund=c('request.refund',id='p',amount=30,key='f')
            self.assertEqual((refund['refunded'],refund['revision']),(30,5))
            self.assertEqual(c('request.spend',id='p',key='s'),spent)
            self.assertEqual(c('request.refund',id='p',amount=30,key='f'),refund)
            rejects(lambda:c('request.refund',id='p',amount=31,key='f'))
            rejects(lambda:c('request.refund',id='p',amount=51,key='unused'))
            c('request.refund',id='p',amount=50,key='unused')
            self.assertEqual(c('department.report',id='café'),dict(budget=100,committed=0,spent=0,available=100))
            snapshot=c('backup')
            rejects(lambda:c('request.import',requests=[dict(payload,id='q'),dict(payload,id='q')]))
            rejects(lambda:c('request.get',id='q'))
            self.assertEqual(c('request.import',requests=[dict(payload,id='q')]),{'imported':1})
            q=c('request.reject',id='q',actor='a',expected_revision=1)
            self.assertEqual((q['status'],q['revision']),('rejected',2))
            c('restore',state=snapshot)
            rejects(lambda:c('request.get',id='q'))
            self.assertEqual(c('request.get',id='p')['refunded'],80)
            rejects(lambda:c('request.create',**dict(payload,id='bad',amount=True)))
        self.assertJourney(flow)

    def test_restore_and_race(self):
        self.c('department.put',id='d',budget=100)
        for id,role in [('r','requester'),('a','approver')]: self.c('member.put',id=id,department='d',role=role)
        for id in ['x','y']: self.c('request.create',id=id,creator='r',amount=70,approvals=1)
        results=self.race(*[('request.approve',dict(id=id,actor='a',expected_revision=1)) for id in ['x','y']])
        self.assertEqual(sum(ok for ok,_ in results),1)
        self.assertEqual(self.c('department.report',id='d')['committed'],70)
        winner=next(id for id in ['x','y'] if self.c('request.get',id=id)['status']=='approved')
        results=self.race(*[('request.spend',dict(id=winner,key='same'))]*2)
        self.assertTrue(all(ok for ok,_ in results))
        self.assertEqual(results[0][1],results[1][1])
        self.assertEqual(self.c('request.get',id=winner)['revision'],3)
        self.assertCorruptions(lambda b:b['state']['requests'][winner].update(refunded=71),lambda b:b['state']['departments']['d'].update(budget=1))
        self.restart()
        self.assertEqual(self.c('department.report',id='d')['spent'],70)
