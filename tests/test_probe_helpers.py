import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
import urllib.error

from goalpilot.probe_helpers import dispatch,rejects,jsonl,json_http

SERVER='''import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def do_GET(self):
  body=json.dumps({'port':self.server.server_port}).encode();self.send_response(200);self.end_headers();self.wfile.write(body)
 def do_POST(self):
  packet=json.loads(self.rfile.read(int(self.headers['Content-Length'])));body=json.dumps(packet).encode();self.send_response(400 if packet.get('bad')else200);self.end_headers();self.wfile.write(body)
with ThreadingHTTPServer(('127.0.0.1',0),Handler)as server:
 print(json.dumps({'port':server.server_port}),flush=True);server.serve_forever()
'''.replace('else200','else 200')


class ProbeHelperTests(unittest.TestCase):
    def test_dispatch_overrides_context_without_duplicate_keywords(self):
        captured=[];call=dispatch(lambda op,data:captured.append((op,data))or data,token='admin',workspace='w')
        self.assertEqual(call('read',token='viewer'),{'workspace':'w','token':'viewer'})
        self.assertEqual(call('read')['token'],'admin')

    def test_rejection_does_not_swallow_unexpected_exceptions(self):
        rejects(lambda:(_ for _ in ()).throw(ValueError('expected')))
        with self.assertRaises(TypeError):rejects(lambda:(_ for _ in ()).throw(TypeError('harness bug')))
        with self.assertRaises(AssertionError):rejects(lambda:42)

    def test_jsonl_uses_real_process_and_recovers_after_error(self):
        program="import sys,json\nfor line in sys.stdin:\n p=json.loads(line);print(json.dumps({'ok':not p.get('bad'),'value':p.get('value')}),flush=True)"
        rows=jsonl([sys.executable,'-c',program],[{'bad':True},{'value':'café 東京'}])
        self.assertEqual(rows,[{'ok':False,'value':None},{'ok':True,'value':'café 東京'}])
        with self.assertRaises(AssertionError):jsonl([sys.executable,'-c','raise SystemExit(2)'],[])
        with self.assertRaises(subprocess.TimeoutExpired):jsonl([sys.executable,'-c','import time;time.sleep(60)'],[],timeout=.05)

    def test_real_http_status_json_and_process_cleanup(self):
        with json_http([sys.executable,'-c',SERVER])as request:
            self.assertGreater(request('GET','/health')['port'],0)
            self.assertEqual(request('POST','/api',{'value':'東京'}),{'value':'東京'})
            self.assertEqual(request('POST','/api',{'bad':True},status=400),{'bad':True})
            with self.assertRaises(AssertionError):request('POST','/api',{'bad':True})
            with self.assertRaises(ValueError):request('GET','//external.example')
        with self.assertRaises(urllib.error.URLError):request('GET','/health')

    def test_partial_startup_line_cannot_hang_verifier(self):
        start=time.monotonic()
        with self.assertRaises(AssertionError):
            with json_http([sys.executable,'-c',"import sys,time;sys.stdout.write('{');sys.stdout.flush();time.sleep(60)"],timeout=.1):pass
        self.assertLess(time.monotonic()-start,2)
