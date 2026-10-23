import unittest
from app import Service
from goalpilot_support import JourneyMixin, rejects

class Workflows(JourneyMixin,unittest.TestCase):
 def setUp(self): self.open_service(Service)
 def test_journey(self):
  def flow(c):
   for m in ['a','b','c','d']: self.assertEqual(c('member.put',id=m,active=True),{'id':m,'active':True})
   p=c('poll.create',id='é',candidates=['z','x','y','x'],quorum=3)
   self.assertEqual(p['candidates'],['x','y','z']); self.assertEqual(p['revision'],1)
   rejects(lambda:c('poll.open',id='é',expected_revision=2))
   self.assertEqual(c('poll.open',id='é',expected_revision=1)['eligible'],['a','b','c','d'])
   c('member.put',id='a',active=False); c('member.put',id='late',active=True)
   c('delegate',poll='é',member='a',to='b'); c('delegate',poll='é',member='b',to='c')
   rejects(lambda:c('delegate',poll='é',member='c',to='a'))
   v={'poll':'é','member':'c','ranking':['y','x'],'key':'1'}
   self.assertEqual(c('vote',**v),{k:v[k] for k in ['poll','member','ranking']})
   self.assertEqual(c('vote',**v),{k:v[k] for k in ['poll','member','ranking']})
   rejects(lambda:c('vote',**dict(v,ranking=['x'])))
   rejects(lambda:c('vote',poll='é',member='a',ranking=['x'],key='a'))
   rejects(lambda:c('vote',poll='é',member='late',ranking=['x'],key='late'))
   rejects(lambda:c('vote.import',votes=[{'poll':'é','member':'d','ranking':['z'],'key':'d'},dict(v,key='other')]))
   self.assertEqual(c('vote.import',votes=[{'poll':'é','member':'d','ranking':['z'],'key':'d'}]),{'imported':1})
   saved=c('backup'); c('poll.close',id='é',expected_revision=2)
   expected={'quorum_met':True,'participating':4,'winner':'y','rounds':[{'counts':{'x':0,'y':3,'z':1},'exhausted':0,'eliminated':None}]}
   self.assertEqual(c('tally',poll='é'),expected)
   self.assertEqual(c('vote',**v),{k:v[k] for k in ['poll','member','ranking']})
   rejects(lambda:c('delegate',poll='é',member='d',to='a'))
   c('restore',state=saved); self.assertEqual(c('poll.get',id='é')['status'],'open')
   c('poll.close',id='é',expected_revision=2); self.assertEqual(c('tally',poll='é'),expected)
   self.assertEqual([p['id'] for p in c('poll.list')],['é'])
  self.assertJourney(flow)
 def test_ties_restore_race(self):
  for m in ['a','b']: self.c('member.put',id=m,active=True)
  self.c('poll.create',id='p',candidates=['a','b','c'],quorum=1); self.c('poll.open',id='p',expected_revision=1)
  votes=[('vote',{'poll':'p','member':'a','ranking':['a'],'key':'k'})]*2
  results=self.race(*votes); self.assertTrue(all(ok for ok,_ in results))
  self.c('vote',poll='p',member='b',ranking=['b'],key='j')
  self.c('poll.close',id='p',expected_revision=2)
  self.assertEqual(self.c('tally',poll='p'),{'quorum_met':True,'participating':2,'winner':'a','rounds':[{'counts':{'a':1,'b':1,'c':0},'exhausted':0,'eliminated':'c'},{'counts':{'a':1,'b':1},'exhausted':0,'eliminated':'b'},{'counts':{'a':1},'exhausted':1,'eliminated':None}]})
  self.assertCorruptions(lambda b:b['state']['polls']['p'].update(revision=1),lambda b:b['state']['polls']['p']['delegations'].update(a='b',b='a'))
