import unittest
from app import Service
from goalpilot_support import JourneyMixin, rejects

class Accounting(JourneyMixin,unittest.TestCase):
 def setUp(self):self.open_service(Service)
 def test_journey(self):
  def flow(c):
   for a in ('cash','sales'):self.assertEqual(c('account.create',id=a,name=a,kind='asset' if a=='cash' else 'income'),{'id':a,'name':a,'kind':'asset' if a=='cash' else 'income'})
   self.assertEqual(c('period.create',id='p',start=0,end=10),dict(id='p',start=0,end=10,status='open',revision=1))
   rejects(lambda:c('period.create',id='q',start=9,end=12))
   lines=[dict(account='cash',debit=123,credit=0),dict(account='sales',debit=0,credit=123)]
   payload=dict(id='e',date=1,lines=lines,key='k')
   expected=dict(id='e',date=1,period='p',lines=lines,status='posted',reversal=None)
   self.assertEqual(c('journal.post',**payload),expected)
   self.assertEqual(c('journal.post',**payload),expected)
   rejects(lambda:c('journal.post',**dict(payload,date=2)))
   rejects(lambda:c('journal.post',**dict(payload,id='bad',key='bad',lines=[dict(lines[0],debit=True),lines[1]])))
   rejects(lambda:c('journal.import',entries=[dict(payload,id='batch',key='batch'),dict(payload,id='bad',key='bad',lines=lines[:1])]))
   self.assertEqual(c('journal.list'),[expected])
   self.assertEqual(c('account.balance',id='cash'),dict(debit=123,credit=0,net=123))
   c('period.close',id='p',expected_revision=1)
   rejects(lambda:c('journal.reverse',id='e',reversal_id='r',date=2,key='r'))
   rejects(lambda:c('period.reopen',id='p',expected_revision=1))
   c('period.reopen',id='p',expected_revision=2)
   backup=c('backup')
   r=c('journal.reverse',id='e',reversal_id='r',date=2,key='r')
   self.assertEqual(r,dict(id='r',date=2,period='p',lines=[dict(account='cash',debit=0,credit=123),dict(account='sales',debit=123,credit=0)],status='posted',reversal=None))
   self.assertEqual(c('journal.post',**payload),expected)
   self.assertEqual(c('journal.reverse',id='e',reversal_id='r',date=2,key='r'),r)
   rejects(lambda:c('journal.reverse',id='r',reversal_id='rr',date=3,key='rr'))
   self.assertEqual(c('journal.get',id='e'),dict(expected,status='reversed',reversal='r'))
   self.assertEqual(c('trial_balance'),[dict(account=a,debit=123,credit=123,net=0) for a in ('cash','sales')])
   c('restore',state=backup)
   self.assertEqual(c('journal.list',period='p',account='cash'),[expected])
   self.assertEqual(c('journal.import',entries=[dict(payload,id='b',key='b')]),{'imported':1})
  self.assertJourney(flow)
 def test_restore_and_race(self):
  for a in ('a','b'):self.c('account.create',id=a,name=a,kind='asset')
  self.c('period.create',id='p',start=0,end=10)
  payload=dict(id='e',date=1,key='k',lines=[dict(account='a',debit=10,credit=0),dict(account='b',debit=0,credit=10)])
  results=self.race(*[('journal.post',payload)]*3)
  self.assertEqual(sum(ok for ok,_ in results),3)
  self.restart();self.assertEqual(self.c('account.balance',id='a')['net'],10)
  self.assertCorruptions(lambda b:b['state']['entries']['e'].update(date=99),lambda b:b['state']['keys'].clear())
