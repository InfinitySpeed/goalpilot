import unittest
from app import Service
from goalpilot_support import JourneyMixin,rejects

class Learning(JourneyMixin,unittest.TestCase):
 def setUp(self):self.open_service(Service)
 def test_journey(self):
  def flow(c):
   for sid in ['z','a','b']:self.assertEqual(c('student.put',id=sid,name='Élève '+sid),{'id':sid,'name':'Élève '+sid})
   self.assertEqual(c('course.put',id='base',prerequisites=[],capacity=1,price=100),{'id':'base','prerequisites':[],'capacity':1,'price':100})
   c('course.put',id='next',prerequisites=['base','base'],capacity=1,price=200)
   rejects(lambda:c('course.put',id='base',prerequisites=['next'],capacity=1,price=100))
   rejects(lambda:c('enroll',student='z',course='next',key='no'))
   a=c('enroll',student='z',course='base',key='a')
   self.assertEqual(a,{'id':a['id'],'student':'z','course':'base','status':'enrolled','price':100,'score':None})
   b=c('enroll',student='a',course='base',key='b'); w=c('enroll',student='b',course='base',key='w')
   self.assertEqual(b['status'],'waiting'); self.assertEqual(w['status'],'waiting')
   self.assertEqual(c('course.report',id='base'),{'enrolled':1,'waiting':2,'completed':0,'cancelled':0,'revenue':100,'waitlist':['a','b']})
   rejects(lambda:c('complete',id=b['id'],score=90))
   rejects(lambda:c('enroll',student='a',course='base',key='another'))
   rejects(lambda:c('enroll',student='b',course='base',key='a'))
   c('course.put',id='base',prerequisites=[],capacity=1,price=300)
   self.assertEqual(c('complete',id=a['id'],score=60),{**a,'status':'completed','score':60})
   self.assertEqual(c('enrollment.get',id=b['id']),{**b,'status':'enrolled'})
   self.assertEqual(c('enroll',student='z',course='base',key='a'),a)
   self.assertEqual(c('cancel',id=b['id']),{'id':b['id'],'status':'cancelled','refund':100})
   self.assertEqual(c('cancel',id=b['id']),{'id':b['id'],'status':'cancelled','refund':100})
   c('complete',id=w['id'],score=59)
   rejects(lambda:c('enroll',student='b',course='next',key='fail'))
   self.assertEqual(c('enroll.import',requests=[{'student':'z','course':'next','key':'next'}]),{'imported':1})
   before=c('enrollment.list')
   rejects(lambda:c('enroll.import',requests=[{'student':'a','course':'base','key':'new'},{'student':'missing','course':'base','key':'bad'}]))
   self.assertEqual(c('enrollment.list'),before)
   snap=c('backup'); c('student.put',id='extra',name='Extra'); c('restore',state=snap); self.assertEqual(c('backup'),snap)
   rejects(lambda:c('course.put',id='bad',prerequisites=[],capacity=True,price=0))
  self.assertJourney(flow)
 def test_restore_and_race(self):
  self.c('student.put',id='s',name='S'); self.c('course.put',id='c',prerequisites=[],capacity=1,price=4)
  results=self.race(*[('enroll',{'student':'s','course':'c','key':'k'})]*2)
  self.assertTrue(all(ok for ok,_ in results)); self.assertEqual(results[0][1],results[1][1]); self.assertEqual(len(self.c('enrollment.list')),1)
  self.restart(); self.assertEqual(self.c('course.report',id='c')['enrolled'],1)
  self.assertCorruptions(lambda b:b.update(format='invalid'),lambda b:b['state']['courses']['c'].update(capacity=0))
