"""Exact-owned hook deduplication; unrelated security/approval hooks stay effective."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

from goalpilot.hook_config import definitions,toml

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('portable_codex_launch',ROOT/'skills/goalpilot-016/scripts/codex_launch.py')
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)


class HookDedupTests(unittest.TestCase):
    def reply(self):
        own=[];global_hooks=[]
        for i,(name,groups)in enumerate(definitions(ROOT/'skills/goalpilot-016/scripts/goalpilot.py').items()):
            handler=groups[0]['hooks'][0]
            h={'command':handler['command'],'source':'sessionFlags','eventName':{'PreToolUse':'preToolUse','PostToolUse':'postToolUse','Stop':'stop'}[name],
               'handlerType':'command','enabled':True,'async':False,'key':'owned-'+str(i),'currentHash':'hash-'+str(i),
               'timeoutSec':handler['timeout'],'matcher':groups[0].get('matcher'),'trustStatus':'untrusted','isManaged':False}
            own.append(h)
            duplicate={**h,'source':'user','key':'global-'+str(i),'trustStatus':'trusted',
                       'command':shlex.join([sys.executable,str(ROOT/'skills/goalpilot/scripts/goalpilot.py'),'hook'])}
            global_hooks.append(duplicate)
        foreign={**global_hooks[-1],'key':'customer-audit','command':'customer-security-review'}
        managed={**foreign,'key':'managed-policy','isManaged':True}
        return {'data':[{'hooks':own+global_hooks+[foreign,managed],'errors':[]}]},own

    def test_only_exact_verified_goalpilot_duplicates_are_selected(self):
        reply,own=self.reply();before=copy.deepcopy(reply)
        self.assertEqual(launcher.duplicate_keys(reply,own,launcher.known_identities()),['global-0','global-1','global-2'])
        self.assertEqual(reply,before)
        for change,value in [('trustStatus','untrusted'),('timeoutSec',999),('async',True),('matcher','.*')]:
            changed=copy.deepcopy(reply);changed['data'][0]['hooks'][3][change]=value
            self.assertNotIn('global-0',launcher.duplicate_keys(changed,own,launcher.known_identities()))

    def test_managed_exact_duplicate_is_refused_instead_of_disabled(self):
        reply,own=self.reply();reply['data'][0]['hooks'][3]['isManaged']=True
        with self.assertRaisesRegex(ValueError,'Managed duplicate'):
            launcher.duplicate_keys(reply,own,launcher.known_identities())

    def test_corrupt_or_unknown_engine_is_never_classified_as_owned(self):
        reply,own=self.reply()
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);(root/'scripts').mkdir();(root/'scripts/goalpilot.py').write_text('print("foreign")')
            for h in reply['data'][0]['hooks'][3:6]:h['command']=shlex.join([sys.executable,str(root/'scripts/goalpilot.py'),'hook'])
            self.assertEqual(launcher.duplicate_keys(reply,own,launcher.known_identities()),[])

    def test_effective_process_configuration_is_verified_without_models_or_global_writes(self):
        reply,own=self.reply();requests=[];overrides=[]
        class RPC:
            def __init__(self,executable,flags):overrides.append(flags)
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def request(self,method,params):
                requests.append(method);result=copy.deepcopy(reply)
                if len(overrides)==2:
                    for h in result['data'][0]['hooks']:
                        if h['key'].startswith('global-'):h['enabled']=False
                        if h['key'].startswith('owned-'):h['trustStatus']='trusted'
                return result
        with tempfile.TemporaryDirectory()as tmp,patch('goalpilot.hook_config.ConfigRPC',RPC),patch('os.execvp')as execute:
            receipt=Path(tmp)/'receipt.json'
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(launcher.main(['--audit-only','--receipt',str(receipt)]),0)
            evidence=json.loads(receipt.read_text());self.assertTrue(evidence['effective_configuration_verified'])
            self.assertEqual(evidence['model_calls'],0);self.assertFalse(evidence['global_settings_changed'])
            execute.assert_not_called()
        self.assertEqual(requests,['hooks/list','hooks/list'])
        import tomllib
        state=tomllib.loads(overrides[-1][-1])['hooks']['state']
        self.assertTrue(state['customer-audit']['enabled']);self.assertNotIn('managed-policy',state)
        self.assertTrue(all(not state['global-'+str(i)]['enabled']for i in range(3)))
        self.assertTrue(all(state['owned-'+str(i)]['enabled']for i in range(3)))


if __name__=='__main__':unittest.main()
