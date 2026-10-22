from pathlib import Path
import sqlite3
from .common import STORAGE,TRANSPORT,STUB
from .specs import SPECS
PUBLIC={
'flowdesk':'''import unittest
from app import Service
import tempfile
from pathlib import Path
class Public(unittest.TestCase):
 def test_open_ticket(self):
  with tempfile.TemporaryDirectory()as t:
   s=Service(Path(t)/'db');s.call('bootstrap',{'workspace':'w','token':'admin'})
   x=s.call('ticket.create',{'workspace':'w','token':'admin','id':'t','title':'Issue'})
   self.assertEqual((x['status'],x['revision']),('open',1))
 def test_viewer_cannot_create(self):
  with tempfile.TemporaryDirectory()as t:
   s=Service(Path(t)/'db');s.call('bootstrap',{'workspace':'w','token':'admin'})
   s.call('member.add',{'workspace':'w','token':'admin','new_token':'reader','role':'viewer'})
   with self.assertRaises(ValueError):s.call('ticket.create',{'workspace':'w','token':'reader','id':'t','title':'Issue'})
''',
'stockroom':'''import unittest,tempfile
from pathlib import Path
from app import Service
class Public(unittest.TestCase):
 def test_receipt(self):
  with tempfile.TemporaryDirectory()as t:
   s=Service(Path(t)/'db');s.call('product.put',{'sku':'x','name':'Product'})
   s.call('warehouse.add',{'id':'a'});s.call('stock.receive',{'sku':'x','warehouse':'a','quantity':5,'key':'r'})
   self.assertEqual(s.call('stock.get',{'sku':'x','warehouse':'a'})['available'],5)
 def test_unknown_order_product(self):
  with tempfile.TemporaryDirectory()as t:
   s=Service(Path(t)/'db')
   with self.assertRaises(ValueError):s.call('order.create',{'id':'o','lines':[{'sku':'missing','quantity':1}]})
''',
'runforge':'''import unittest,tempfile
from pathlib import Path
from app import Service
class Public(unittest.TestCase):
 def test_claim_and_success(self):
  with tempfile.TemporaryDirectory()as t:
   s=Service(Path(t)/'db');s.call('workflow.put',{'id':'w','nodes':[{'id':'a','needs':[]}]})
   s.call('run.start',{'workflow':'w','id':'r','key':'k'});c=s.call('job.claim',{'worker':'x','now':0,'lease':10})
   x=s.call('job.succeed',{'run':'r','node':'a','receipt':c['receipt'],'now':1,'result':42})
   self.assertEqual(x['status'],'succeeded')
 def test_cycle_rejected(self):
  with tempfile.TemporaryDirectory()as t:
   s=Service(Path(t)/'db')
   with self.assertRaises(ValueError):s.call('workflow.put',{'id':'w','nodes':[{'id':'a','needs':['a']}]})
'''}

def materialize(repo,name,reference=False):
    repo=Path(repo);repo.mkdir(parents=True,exist_ok=True)
    for filename,content in {'README.md':SPECS[name],'storage.py':STORAGE,'app.py':'from storage import Service\n','transport.py':TRANSPORT,'engine.py':Path(__file__).with_name('reference_'+name+'.py').read_text()if reference else STUB.format(name=name)}.items():
        (repo/filename).write_text(content)
    (repo/'tests').mkdir(exist_ok=True);(repo/'tests/test_public.py').write_text(PUBLIC[name]);(repo/'tests/__init__.py').write_text('')
    (repo/'USER_NOTES.txt').write_text('Original customer data: café 東京.\n');(repo/'data').mkdir(exist_ok=True)
    with sqlite3.connect(repo/'data/original.sqlite')as db:db.execute('CREATE TABLE notes(id INTEGER PRIMARY KEY,value TEXT)');db.execute('INSERT INTO notes VALUES(41,?)',('Keep my unrelated table.',))
    return repo
