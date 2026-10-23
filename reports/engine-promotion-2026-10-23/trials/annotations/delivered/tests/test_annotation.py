import unittest
from app import Service
from goalpilot_support import JourneyMixin,rejects

class Annotation(JourneyMixin,unittest.TestCase):
 def setUp(self):self.open_service(Service)
 def test_journey(self):
  def flow(c):
   self.assertEqual(c('dataset.create',id='d',labels=['oui','non','oui'],reviews=2),{'id':'d','labels':['non','oui'],'reviews':2})
   for a in ['a','b','c']:self.assertEqual(c('annotator.put',id=a,active=True),{'id':a,'active':True})
   added=c('item.add',dataset='d',id='i',payload={'é':[1]})
   self.assertEqual(added,dict(id='i',dataset='d',payload={'é':[1]},status='pending',votes=[],revision=1,consensus=None))
   x=c('claim',dataset='d',annotator='a',now=0,lease=5);y=c('claim',dataset='d',annotator='b',now=0,lease=10)
   self.assertEqual(x['item'],added);self.assertEqual(x['expires'],5);self.assertNotEqual(x['receipt'],y['receipt'])
   self.assertIsNone(c('claim',dataset='d',annotator='c',now=1,lease=5))
   rejects(lambda:c('submit',dataset='d',item='i',annotator='a',receipt=x['receipt'],now=5,label='oui'))
   z=c('claim',dataset='d',annotator='a',now=5,lease=10)
   rejects(lambda:c('submit',dataset='d',item='i',annotator='a',receipt=x['receipt'],now=6,label='oui'))
   c('annotator.put',id='a',active=False)
   rejects(lambda:c('submit',dataset='d',item='i',annotator='a',receipt=z['receipt'],now=6,label='oui'))
   c('annotator.put',id='a',active=True)
   one=c('submit',dataset='d',item='i',annotator='a',receipt=z['receipt'],now=6,label='oui')
   self.assertEqual(one['status'],'reviewing');self.assertEqual(one['revision'],2)
   backup=c('backup');c('restore',state=backup)
   done=c('submit',dataset='d',item='i',annotator='b',receipt=y['receipt'],now=7,label='non')
   self.assertEqual(done['votes'],[{'annotator':'a','label':'oui'},{'annotator':'b','label':'non'}]);self.assertIsNone(done['consensus'])
   self.assertEqual(c('report',dataset='d'),dict(pending=0,reviewing=0,complete=1,disputed=1))
   rejects(lambda:c('item.reopen',dataset='d',id='i',expected_revision=2))
   self.assertEqual(c('item.reopen',dataset='d',id='i',expected_revision=3)['revision'],4)
   self.assertEqual(c('history',dataset='d',id='i'),[{'votes':done['votes'],'consensus':None}])
   rejects(lambda:c('item.import',dataset='d',items=[{'id':'new','payload':None},{'id':'i','payload':0}]))
   self.assertEqual(c('item.import',dataset='d',items=[{'id':'new','payload':None}]),{'imported':1})
   self.assertEqual([i['id'] for i in c('item.list',dataset='d',status='pending')],['i','new'])
   rejects(lambda:c('dataset.create',id='bad',labels=['x'],reviews=True))
  self.assertJourney(flow)
 def test_race_restore(self):
  self.c('dataset.create',id='d',labels=['x'],reviews=1)
  self.c('item.add',dataset='d',id='i',payload=None)
  for a in ['a','b']:self.c('annotator.put',id=a,active=True)
  results=self.race(*[('claim',dict(dataset='d',annotator=a,now=0,lease=10)) for a in ['a','b']])
  self.assertEqual(sum(ok and result is not None for ok,result in results),1)
  self.restart()
  self.assertIsNone(self.c('claim',dataset='d',annotator='b' if results[0][1] else 'a',now=1,lease=10))
  self.assertCorruptions(lambda b:b['state']['datasets']['d']['items']['i'].update(revision=999))
