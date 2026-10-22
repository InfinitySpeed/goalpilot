import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from goalpilot.adapters import AgentResult
from goalpilot.finish import continue_finish, parse_audit, run_finish
from goalpilot.model import ContractError
from tests.test_finish import Auditor,Builder


class FinishEdgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.repo=self.root/'repo';self.repo.mkdir();self.run=self.root/'run'

    def test_audit_retry_on_explicit_resume_preserves_previous_calls(self):
        builder=Builder();auditor=Auditor(code=1)
        with self.assertRaises(ContractError):run_finish('Deliver 42',self.repo,self.run,
            wall_seconds=30,adapter=builder,auditor=auditor,max_calls=5)
        auditor.code=0
        state=continue_finish(self.run,adapter=builder,auditor=auditor)
        self.assertEqual([c['strategy'] for c in state['calls']],['build','audit','audit','implement'])
        self.assertEqual(state['usage']['total_tokens'],440)
        self.assertEqual(builder.calls,2)

    def test_repeated_unfinished_audits_cannot_reset_call_cap(self):
        builder=Builder();auditor=Auditor(code=1)
        with self.assertRaises(ContractError):run_finish('Deliver 42',self.repo,self.run,
            wall_seconds=30,adapter=builder,auditor=auditor,max_calls=3)
        for _ in range(3):
            with self.assertRaises(ContractError):continue_finish(self.run,adapter=builder,auditor=auditor)
        self.assertEqual(auditor.calls,2)
        self.assertEqual(len(json.loads((self.run/'finish-run.json').read_text())['calls']),3)

    def test_resume_refuses_changed_budget_before_remote_calls(self):
        builder=Builder();auditor=Auditor()
        run_finish('Deliver 42',self.repo,self.run,wall_seconds=30,adapter=builder,auditor=auditor)
        with self.assertRaises(ContractError):run_finish('Deliver 42',self.repo,self.run,
            wall_seconds=60,adapter=builder,auditor=auditor,resume=True)
        self.assertEqual(builder.calls,2)

    def test_original_contract_survives_builder_rewriting_readme(self):
        (self.repo/'README.md').write_text('Required full behavior')
        class ReadmeBuilder(Builder):
            def execute(self,*args,**kwargs):
                (args[1]/'README.md').write_text('Simplified behavior')
                return super().execute(*args,**kwargs)
        auditor=Auditor()
        run_finish('Deliver 42',self.repo,self.run,wall_seconds=30,adapter=ReadmeBuilder(),auditor=auditor)
        self.assertIn('Required full behavior',auditor.prompt)
        self.assertNotIn('Simplified behavior',auditor.prompt)

    def test_formatting_fences_accepted_without_extra_call(self):
        raw=json.dumps({'assumptions':[],'blockers':[], 'limitations':[],'requirements':[
            {'id':'x','requirement':'behavior','source':'goal','python':'assert 1 == 1'}]})
        self.assertEqual(parse_audit('```json\n'+raw+'\n```')['requirements'][0]['id'],'x')

    def test_cli_dispatch_uses_finish_by_default_and_fast_is_explicit(self):
        from goalpilot.cli import main
        from tests.test_finish import result
        # Real offline state, mocked only at CLI boundary: exercise actual parser.
        state=run_finish('Deliver 42',self.repo,self.run,wall_seconds=30,adapter=Builder(),auditor=Auditor())
        args=['go','Deliver 42','--repo',str(self.repo),'--run-dir',str(self.root/'another')]
        with patch('goalpilot.finish.run_finish',return_value=state) as finish,patch('goalpilot.autopilot.run_autopilot',return_value=state) as fast:
            with patch('builtins.print'):self.assertEqual(main(args),0)
            self.assertEqual(finish.call_count,1);self.assertEqual(fast.call_count,0)
            with patch('builtins.print'):self.assertEqual(main(args+['--fast']),0)
            self.assertEqual(fast.call_count,1)


if __name__=='__main__':unittest.main()
