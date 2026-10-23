import unittest
from app import Service
from goalpilot_support import JourneyMixin, rejects

class QueueTests(JourneyMixin,unittest.TestCase):
 def setUp(self): self.open_service(Service)
 def test_journey(self):
  def flow(c):
   self.assertEqual(c('queue.create',id='q',max_attempts=2,retry_delay=3),{'id':'q','max_attempts':2,'retry_delay':3})
   p=dict(queue='q',id='a',payload={'é':[1]},key='k')
   original=c('message.publish',**p)
   self.assertEqual(original,dict(id='a',queue='q',payload={'é':[1]},status='pending',attempts=0,priority=0,not_before=0,receipt=None,worker=None))
   self.assertEqual(c('message.publish',**p),original)
   rejects(lambda:c('message.publish',**dict(p,payload=2)))
   rejects(lambda:c('message.publish',**dict(p,key='bad',priority=True)))
   rejects(lambda:c('publish.import',messages=[dict(p,id='b',key='b'),dict(p,key='conflict')]))
   self.assertEqual(c('message.list',queue='q'),[original])
   leased=c('claim',queue='q',worker='w',now=0,lease=2,limit=2)
   self.assertEqual(len(leased),1); a=leased[0]
   self.assertEqual(a,dict(original,status='leased',attempts=1,receipt=a['receipt'],worker='w',expires=2))
   self.assertEqual(c('message.publish',**p),original)
   rejects(lambda:c('ack',queue='q',id='a',receipt=a['receipt'],now=2))
   self.assertEqual(c('message.get',queue='q',id='a'),a)
   self.assertEqual(c('queue.stats',queue='q',now=2),dict(pending=1,leased=0,done=0,dead=0,cancelled=0))
   self.assertEqual(c('claim',queue='q',worker='w',now=4,lease=2,limit=1),[])
   b=c('claim',queue='q',worker='w',now=5,lease=2,limit=1)[0]
   self.assertNotEqual(a['receipt'],b['receipt'])
   rejects(lambda:c('nack',queue='q',id='a',receipt=a['receipt'],now=5))
   dead=c('nack',queue='q',id='a',receipt=b['receipt'],now=5)
   self.assertEqual(dead['status'],'dead'); self.assertNotIn('expires',dead)
   self.assertEqual(c('redrive',queue='q',id='a',now=8)['attempts'],0)
   snapshot=c('backup')
   c('message.cancel',queue='q',id='a')
   c('restore',state=snapshot)
   third=c('claim',queue='q',worker='x',now=8,lease=4,limit=1)[0]
   self.assertNotIn(third['receipt'],[a['receipt'],b['receipt']])
   self.assertEqual(c('ack',queue='q',id='a',receipt=third['receipt'],now=9)['status'],'done')
   rejects(lambda:c('ack',queue='q',id='a',receipt=third['receipt'],now=9))
   self.assertEqual(c('publish.import',messages=[dict(p,id='z',key='z'),dict(p,id='b',key='b',priority=2)]),{'imported':2})
   self.assertEqual([m['id'] for m in c('claim',queue='q',worker='w',now=9,lease=1,limit=2)],['b','z'])
  self.assertJourney(flow)
 def test_restore_and_race(self):
  self.c('queue.create',id='q',max_attempts=1,retry_delay=0)
  p=dict(queue='q',id='a',payload=None,key='k')
  results=self.race(*[('message.publish',p)]*2)
  self.assertTrue(all(ok for ok,_ in results)); self.assertEqual(results[0][1],results[1][1])
  self.restart(); self.assertEqual(len(self.c('message.list',queue='q')),1)
  results=self.race(*[('claim',dict(queue='q',worker='w',now=0,lease=1,limit=1))]*2)
  self.assertTrue(all(ok for ok,_ in results)); self.assertEqual(sorted(len(r) for _,r in results),[0,1])
  self.assertCorruptions(lambda b:b['state']['messages']['q']['a'].update(attempts=99),lambda b:b['state']['queues'].clear())
  self.assertEqual(self.c('queue.stats',queue='q',now=1)['dead'],1)
