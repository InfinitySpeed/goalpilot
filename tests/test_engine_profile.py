import json
from pathlib import Path
import sys
import tempfile
import unittest
from tests.test_v2 import SHIM
from tools.run_engine_profile import ProfileAdapter, parser, SCOPE


class EngineProfileTests(unittest.TestCase):
    def test_benchmark_permissions_effort_and_prompt_reach_the_wire(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';repo.mkdir();shim=root/'codex'
            shim.write_text('#!'+sys.executable+'\n'+SHIM.replace("=='workspace-write'","=='danger-full-access'"));shim.chmod(0o700)
            with ProfileAdapter('fixture-model',executable=str(shim),effort='low',sandbox='danger-full-access')as adapter:
                result=adapter.execute('Original goal',repo,3,root/'call')
            self.assertEqual(result.returncode,0)
            packets=[json.loads(line)['packet']for line in (root/'call/events.jsonl').read_text().splitlines()]
            thread=next(x['params']for x in packets if x.get('method')=='thread/start')
            self.assertEqual(thread['sandbox'],'danger-full-access')
            self.assertEqual(thread['config']['model_reasoning_effort'],'low')
            turn=next(x['params']for x in packets if x.get('method')=='turn/start')
            self.assertIn(SCOPE+'Original goal',turn['input'][0]['text'])
            self.assertEqual(turn['effort'],'low')

    def test_full_access_requires_an_explicit_cli_choice(self):
        args=parser().parse_args(['--goal','x','--repo','.','--run-dir','/tmp/evidence'])
        self.assertEqual(args.sandbox,'workspace-write')
        self.assertEqual((args.max_calls,args.wall_seconds,args.max_tokens),(2,600,700000))
        with self.assertRaises(ValueError):ProfileAdapter(sandbox='unknown')
