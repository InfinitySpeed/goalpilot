import json,tempfile,unittest
from pathlib import Path
from goalpilot.audit_recovery import prefix_fields,combine
from goalpilot.finish import run_finish,continue_finish
from goalpilot.adapters import AgentResult
from tests import test_finish as fixture


def requirement(name='answer'):
    return {'id':name,'requirement':'Deliver 42','source':'Original goal','python':"from pathlib import Path\nassert Path('answer').read_text()=='42'\n"}


def audit(requirements):return {'assumptions':[],'blockers':[],'limitations':[],'requirements':requirements}


class PartialJSONTests(unittest.TestCase):
    def test_truncated_program_is_never_retained_as_executable(self):
        text=json.dumps(audit([requirement(),requirement('truncated')]))
        point=text.index('truncated')+len('truncated')
        prefix=prefix_fields(text[:point]);self.assertEqual(prefix['requirements'],[requirement()])

    def test_brackets_inside_escaped_python_do_not_confuse_checkpoint(self):
        r=requirement();r['python']='assert {"brackets": "[] } \\\""}["brackets"].startswith("[")\n'
        prefix=prefix_fields(json.dumps(audit([r]))[:-1]);self.assertEqual(prefix['requirements'],[r])

    def test_blockers_are_retained_and_duplicate_ids_never_drop_a_check(self):
        prefix=audit([requirement()]);prefix['blockers']=['Essential service missing']
        other=requirement();other['python']='assert False'
        result=combine(prefix,audit([other]));self.assertEqual(result['blockers'],prefix['blockers']);self.assertEqual(len(result['requirements']),2);self.assertEqual(len({r['id']for r in result['requirements']}),2)


class RecoveryTests(unittest.TestCase):
    setUp=fixture.FinishTests.setUp
    def reviewer(self,interrupt=False):
        class Reviewer:
            simulated=True;calls=0
            def execute(worker,prompt,repo,timeout,log_dir,**kwargs):
                worker.calls+=1
                if worker.calls==1:
                    text=json.dumps(audit([requirement(),requirement('partial')]))
                    text=text[:text.index('partial')+3];log_dir.mkdir(parents=True,exist_ok=True)
                    event={'packet':{'method':'item/agentMessage/delta','params':{'itemId':'a','delta':text}}}
                    (log_dir/'events.jsonl').write_text(json.dumps(event)+'\n')
                    return AgentResult(124,'No final delivery',.001,{'input_tokens':10,'output_tokens':2,'cached_input_tokens':0},timed_out=True,usage_complete=False,simulated=True)
                if interrupt and worker.calls==2:raise KeyboardInterrupt()
                self.assertIn('do NOT repeat',prompt)
                return fixture.result(json.dumps(audit([])))
        return Reviewer()

    def builder(self):
        class Worker(fixture.Builder):
            def execute(worker,*args,**kwargs):
                result=super().execute(*args,**kwargs);(args[1]/'answer').write_text('42');return result
        return Worker()

    def test_interrupted_review_recovers_automatically_without_rebuilding_or_dropping_checks(self):
        worker=self.builder();reviewer=self.reviewer()
        state=run_finish('Deliver 42',self.repo,self.run,wall_seconds=120,max_calls=6,adapter=worker,auditor=reviewer)
        self.assertEqual(state['status'],'scope_passed');self.assertEqual(worker.calls,1);self.assertEqual(reviewer.calls,2)
        self.assertEqual([c['strategy']for c in state['calls']],['build','audit','audit-recovery'])
        self.assertFalse(state['usage']['usage_complete']);self.assertEqual(len(state['contract']['checks']),1)
        self.assertTrue(state['verifications'][-1]['checks'][0]['passed'])

    def test_recovery_resume_preserves_prefix_and_charged_call_reservations(self):
        worker=self.builder();reviewer=self.reviewer(True)
        with self.assertRaises(KeyboardInterrupt):run_finish('Deliver 42',self.repo,self.run,wall_seconds=300,max_calls=6,adapter=worker,auditor=reviewer)
        state=continue_finish(self.run,adapter=worker,auditor=reviewer)
        self.assertEqual(state['status'],'scope_passed');self.assertEqual(worker.calls,1);self.assertEqual(reviewer.calls,3)
        self.assertEqual([c['strategy']for c in state['calls']],['build','audit','audit-recovery','audit-recovery'])
        self.assertGreaterEqual(state['active_seconds'],89)

    def test_complete_executable_audit_survives_transport_timeout_without_extra_call(self):
        class Reviewer(fixture.Auditor):
            def execute(worker,*a,**kw):
                r=super().execute(*a,**kw);r.returncode=124;r.timed_out=True;r.usage_complete=False;return r
        worker=self.builder();reviewer=Reviewer();state=run_finish('Deliver 42',self.repo,self.run,wall_seconds=30,adapter=worker,auditor=reviewer)
        self.assertEqual(state['status'],'scope_passed');self.assertEqual(reviewer.calls,1);self.assertFalse(state['usage']['usage_complete'])
