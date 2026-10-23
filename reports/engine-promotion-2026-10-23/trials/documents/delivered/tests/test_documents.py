import unittest
from app import Service
from goalpilot_support import JourneyMixin, rejects


class Documents(JourneyMixin,unittest.TestCase):
    def setUp(self):self.open_service(Service)

    def test_journey(self):
        def flow(c):
            a=c('document.create',id='café',fields={'title':'A','body':''})
            self.assertEqual(a,{'id':'café','revision':1,'fields':{'title':'A','body':''},'status':'draft','approved':[],'published':0})
            rejects(lambda:c('document.live',id='café'))
            b=c('branch.create',id='b',document='café')
            self.assertEqual(b,{'id':'b','document':'café','base_revision':1,'revision':1,'fields':a['fields'],'status':'open'})
            c('branch.edit',id='b',expected_revision=1,changes={'title':'B'})
            c('document.edit',id='café',expected_revision=1,changes={'body':'live'})
            a=c('branch.merge',id='b',expected_revision=2,document_revision=2)
            self.assertEqual(a['fields'],{'title':'B','body':'live'}); self.assertEqual(a['revision'],3)
            self.assertEqual(c('branch.get',id='b')['status'],'merged')
            rejects(lambda:c('branch.edit',id='b',expected_revision=3,changes={'x':'x'}))
            rejects(lambda:c('document.publish',id='café',expected_revision=3))
            c('document.approve',id='café',actor='alice',expected_revision=3)
            a=c('document.approve',id='café',actor='alice',expected_revision=3)
            self.assertEqual(a['approved'],['alice']); self.assertEqual(a['revision'],3)
            c('document.approve',id='café',actor='bob',expected_revision=3)
            c('document.publish',id='café',expected_revision=3)
            c('document.edit',id='café',expected_revision=3,changes={'title':'new'})
            self.assertEqual(c('document.live',id='café'),{'id':'café','revision':3,'fields':{'title':'B','body':'live'}})
            c('branch.create',id='conflict',document='café')
            c('branch.edit',id='conflict',expected_revision=1,changes={'title':'branch'})
            c('document.edit',id='café',expected_revision=4,changes={'title':'other'})
            rejects(lambda:c('branch.merge',id='conflict',expected_revision=2,document_revision=5))
            c('branch.edit',id='conflict',expected_revision=2,changes={'title':'other'})
            self.assertEqual(c('branch.merge',id='conflict',expected_revision=3,document_revision=5)['revision'],6)
            rejects(lambda:c('document.import',documents=[{'id':'extra','fields':{'x':''}},{'id':'café','fields':{'x':''}}]))
            rejects(lambda:c('document.get',id='extra'))
            self.assertEqual(c('document.import',documents=[{'id':'extra','fields':{'x':''}}]),{'imported':1})
            self.assertEqual([x['id'] for x in c('document.list')],['café','extra'])
            for changes in ({}, {'':'x'}, {'x':1}):
                rejects(lambda:c('document.edit',id='café',expected_revision=6,changes=changes))
            rejects(lambda:c('document.edit',id='café',expected_revision=True,changes={'x':''}))
            snap=c('backup'); c('document.edit',id='café',expected_revision=6,changes={'x':'temporary'})
            c('restore',state=snap)
            self.assertEqual(c('document.get',id='café')['revision'],6)
        self.assertJourney(flow)

    def test_restore_and_race(self):
        self.c('document.create',id='d',fields={'x':'0'})
        self.assertCorruptions(lambda b:b['state']['documents']['d'].update(revision=90),lambda b:b['state']['documents']['d']['fields'].update(x=3))
        outcomes=self.race(*[('document.edit',{'id':'d','expected_revision':1,'changes':{'x':str(i)}}) for i in range(2)])
        self.assertEqual(sum(ok for ok,_ in outcomes),1)
        self.restart(); self.assertEqual(self.c('document.get',id='d')['revision'],2)
