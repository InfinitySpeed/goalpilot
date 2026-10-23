import hashlib
import unittest
from app import Service
from goalpilot_support import JourneyMixin, rejects

class Flags(JourneyMixin,unittest.TestCase):
 def setUp(self):self.open_service(Service)
 def test_journey(self):
  def flow(c):
   c('environment.create',id='prod'); c('environment.create',id='dev')
   c('segment.put',environment='prod',id='team',members=['é','é'])
   f=c('flag.create',environment='prod',id='x',default=False)
   self.assertEqual(f,dict(id='x',environment='prod',revision=1,published=0,enabled=False,default=False,rules=[]))
   c('flag.create',environment='dev',id='x',default=True)
   def p(op,**kw):return c(op,environment='prod',id='x',**kw)
   def ev(value,revision):
    self.assertEqual(p('flag.evaluate',user='é'),dict(value=value,revision=revision,bucket=int.from_bytes(hashlib.sha256('prod|x|é'.encode()).digest()[:8],'big')%100))
   ev(False,0)
   rules=[dict(segment='team',percent=100,value=True)]
   p('flag.update',expected_revision=1,enabled=True,rules=rules); ev(False,0)
   p('flag.publish',expected_revision=2); p('flag.publish',expected_revision=2); ev(True,2)
   c('segment.put',environment='prod',id='team',members=[]); ev(False,2)
   c('segment.put',environment='prod',id='team',members=['é']); ev(True,2)
   p('flag.update',expected_revision=2,enabled=False,rules=[]); ev(True,2)
   p('flag.publish',expected_revision=3); ev(False,3)
   p('flag.rollback',expected_revision=3,revision=2); ev(True,4)
   for op,kw in [('flag.update',dict(expected_revision=3,enabled=True,rules=[])),('flag.rollback',dict(expected_revision=4,revision=99)),('flag.update',dict(expected_revision=4,enabled=True,rules=[dict(segment='missing',percent=100,value=True)])),('flag.update',dict(expected_revision=4,enabled=True,rules=[dict(segment=None,percent=True,value=True)]))]:rejects(lambda:p(op,**kw))
   rejects(lambda:c('segment.delete',environment='prod',id='team'))
   self.assertEqual(c('flag.evaluate',environment='dev',id='x',user='é')['value'],True)
   rejects(lambda:c('flag.import',environment='prod',flags=[dict(id='a',default=True),dict(id='x',default=True)]))
   self.assertEqual([f['id'] for f in c('flag.list',environment='prod')],['x'])
   self.assertEqual(c('flag.import',environment='prod',flags=[dict(id='b',default=True),dict(id='a',default=False)]),{'imported':2})
   events=c('audit.list',environment='prod')
   self.assertEqual([e['kind'] for e in events],['flag.created','flag.updated','flag.published','flag.updated','flag.published','flag.rolled_back','flag.created','flag.created'])
   self.assertEqual([e['sequence'] for e in events],list(range(1,9)))
   backup=c('backup'); c('environment.create',id='temp'); c('restore',state=backup)
   rejects(lambda:c('flag.list',environment='temp')); ev(True,4)
  self.assertJourney(flow)
 def test_restore_and_race(self):
  self.c('environment.create',id='p'); self.c('flag.create',environment='p',id='f',default=False)
  results=self.race(*[('flag.update',dict(environment='p',id='f',expected_revision=1,enabled=True,rules=[]))]*2)
  self.assertEqual(sum(ok for ok,_ in results),1)
  self.assertEqual(self.c('flag.get',environment='p',id='f')['revision'],2)
  self.assertCorruptions(lambda b:b['state']['environments']['p']['flags']['f']['draft'].update(revision=99))
