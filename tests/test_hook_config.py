"""Trust only authored exact hooks; no global configuration writes or model calls."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from goalpilot.hook_config import ConfigRPC,definitions,install,review,toml
from goalpilot.model import ContractError


class HookConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.launcher=self.root/'gp.py';self.launcher.write_text('# launcher fixture')
        self.defs=definitions(self.launcher)
    def reply(self,source='sessionFlags'):
        rows=[]
        for i,(name,groups)in enumerate(self.defs.items()):
            handler=groups[0]['hooks'][0]
            rows.append({'command':handler['command'],'source':source,'eventName':{'PreToolUse':'preToolUse','PostToolUse':'postToolUse','Stop':'stop'}[name],
                         'handlerType':'command','enabled':True,'async':False,'key':f'owned-{i}','currentHash':f'hash-{i}',
                         'timeoutSec':handler['timeout'],'matcher':groups[0].get('matcher'),'trustStatus':'untrusted','isManaged':False})
        return {'data':[{'hooks':rows,'errors':[]}]}
    def test_review_trusts_exact_owned_and_preserves_existing_trust_without_approving_foreign(self):
        r=self.reply();foreign={'command':'unrelated','source':'user','handlerType':'command','key':'foreign','currentHash':'f','enabled':True,'isManaged':False,'trustStatus':'untrusted'}
        r['data'][0]['hooks'].append(foreign)
        own,state=review(r,self.defs,source='sessionFlags');self.assertEqual(len(own),3);self.assertNotIn('foreign',state)
        foreign['trustStatus']='trusted';_,state=review(r,self.defs,source='sessionFlags');self.assertEqual(state['foreign']['trusted_hash'],'f')
        for change in [('command','malicious replacement'),('timeoutSec',999),('matcher','.*'),('async',True)]:
            bad=self.reply();bad['data'][0]['hooks'][0][change[0]]=change[1]
            with self.assertRaises(ContractError):review(bad,self.defs,source='sessionFlags')
    def test_configuration_rpc_cannot_launch_any_model_thread_or_arbitrary_method(self):
        rpc=ConfigRPC('not-executed')
        for method in ('thread/start','turn/start','thread/goal/set','command/exec','account/read'):
            with self.assertRaises(ContractError):rpc.request(method,{})
    def test_toml_roundtrip_keeps_special_hook_keys_and_values(self):
        import tomllib
        value={'/owned/path:stop.0':{'trusted_hash':'a"b\\c','enabled':True}}
        self.assertEqual(tomllib.loads('state='+toml(value))['state'],value)
    def test_install_preserves_foreign_hooks_and_reviews_only_owned_hashes(self):
        import json
        folder=self.root/'codex';folder.mkdir();path=folder/'hooks.json'
        foreign={'hooks':{'Stop':[{'hooks':[{'type':'command','command':'unchanged-user-hook'}]}]},'description':'Customer metadata'}
        raw=json.dumps(foreign);path.write_text(raw)
        reply=self.reply('user');edits=[]
        class FixtureRPC:
            instances=0
            def __init__(self,*args):pass
            def __enter__(self):FixtureRPC.instances+=1;return self
            def __exit__(self,*args):pass
            def request(self,method,params):
                if method=='hooks/list':
                    result=copy.deepcopy(reply)
                    if FixtureRPC.instances>=2:
                        for h in result['data'][0]['hooks']:h['trustStatus']='trusted'
                    return result
                self_outer=edits;self_outer.extend(params['edits']);return {}
        with patch('goalpilot.hook_config.ConfigRPC',FixtureRPC):result=install(self.launcher,codex_dir=folder)
        self.assertEqual(result['status'],'installed');self.assertEqual(len(edits),3)
        installed=json.loads(path.read_text());self.assertEqual(installed['description'],'Customer metadata')
        self.assertEqual(installed['hooks']['Stop'][0],foreign['hooks']['Stop'][0])
        self.assertEqual(json.loads((folder/'goalpilot-hooks-backup.json').read_text())['original_hooks_json'],raw)
