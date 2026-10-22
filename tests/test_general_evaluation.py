import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.general.campaign import plan,run_next,recover,telemetry,outcome
from evaluation.general.preflight import run as preflight
from evaluation.general.report import summarize
from goalpilot.adapters import AgentResult
from goalpilot.model import ContractError


class GeneralEvaluationTests(unittest.TestCase):
    def manifest(self):
        return {'kind':'test','model':'gpt-6.1-sol','cases':[{'name':'a'},{'name':'b'},{'name':'c'}],
            'repeats':2,'order':list(range(12)),'decision_rule':'fixed','scope':'test'}
    def records(self):
        rows=[]
        for case in ('a','b','c'):
            for repeat in (1,2):
                for mode in ('direct','goalpilot'):
                    rows.append({'id':f'{case}-{repeat}-{mode}','case':case,'repeat':repeat,'mode':mode,
                        'infrastructure_interrupted':False,'autonomous_success':True,'artifact_success':True,
                        'blocker_resolved':True,'stable_on_new_inputs':True,'seconds':100 if mode=='direct' else 80,
                        'new_agent_turns':1,'human_inputs_after_start':0,
                        'usage':{'total_tokens':1000,'cached_input_tokens':500,'usage_complete':True},
                        'telemetry':{'repeated_identical_failed_commands':0,'observed_models':['gpt-6.1-sol']}})
        return rows
    def test_equal_quality_speed_gain_and_repetitions(self):
        r=summarize(self.manifest(),self.records())
        self.assertTrue(r['primary_threshold_met'])
        self.assertEqual(r['complete_eligible_pairs'],6)
        self.assertEqual(r['unique_projects'],3)
        self.assertAlmostEqual(r['time_reduction_percent'],20)
    def test_real_completion_gain_is_separate_from_time(self):
        rows=self.records()
        for x in rows:x['seconds']=100
        for x in [x for x in rows if x['mode']=='direct'][:2]:x['autonomous_success']=False
        self.assertTrue(summarize(self.manifest(),rows)['primary_threshold_met'])
        self.assertEqual(summarize(self.manifest(),rows)['quality_wins'],2)
    def test_interruptions_and_simulations_cannot_prove_primary(self):
        for variant in ('missing','infra','simulated','regression'):
            rows=self.records()
            if variant=='missing':rows.pop()
            elif variant=='infra':rows[0]['infrastructure_interrupted']=True;rows[0]['seconds']=None
            elif variant=='simulated':rows[0]['simulated']=True
            else:rows[1]['autonomous_success']=False
            self.assertFalse(summarize(self.manifest(),rows)['primary_threshold_met'],variant)
    def test_cost_per_success_includes_failed_trials_and_missing_usage_blocks_cost(self):
        rows=self.records();rows[0]['autonomous_success']=False
        r=summarize(self.manifest(),rows)
        self.assertEqual(r['groups']['direct']['reported_tokens_per_success'],1200)
        rows[0]['usage']['usage_complete']=False
        r=summarize(self.manifest(),rows)
        self.assertIsNone(r['groups']['direct']['reported_tokens_per_success'])
        self.assertIsNone(r['non_cached_token_reduction_percent'])
    def test_recovery_uses_thread_cumulative_max_without_double_counting(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            for i,value in enumerate((100,180)):
                p=root/str(i);p.mkdir()
                packet={'method':'thread/tokenUsage/updated','params':{'threadId':'same','turnId':str(i),'tokenUsage':{'total':{'inputTokens':value,'outputTokens':10,'cachedInputTokens':50}}}}
                (p/'events.jsonl').write_text(json.dumps({'packet':packet})+'\n')
            self.assertEqual(telemetry(root)['usage_lower_bound']['input_tokens'],180)
    def test_live_flag_required_without_any_files_or_remote_calls(self):
        with self.assertRaises(ContractError):run_next(Path('/missing'),live=False)
    def test_null_command_output_and_completed_failed_judgments_are_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            packet={'method':'item/completed','params':{'item':{'type':'commandExecution','command':'tool','aggregatedOutput':None,'exitCode':1}}}
            (root/'events.jsonl').write_text(json.dumps({'packet':packet})+'\n')
            self.assertEqual(telemetry(root)['command_count'],1)
            failed=[{'id':'blocker','passed':False,'error':'original failure','seconds':.1,'seed':1}]
            for i in (1,2):(root/f'judge-{i}.json').write_text(json.dumps(failed))
            with patch('evaluation.general.campaign.evaluate',side_effect=AssertionError('must not rejudge')):
                checks,_=outcome({'name':'unused'},root,root)
            self.assertEqual(len(checks),2)
            self.assertTrue(all(not x['passed'] for x in checks))
    def test_reference_preflight_is_attainable_and_rejects_semantic_faults(self):
        data=preflight()
        self.assertEqual(data['model_calls'],0)
        self.assertEqual(sum(x['reference_checks_passed'] for x in data['cases']),12)
        self.assertTrue(all(x['semantic_mutation_rejected_by'] for x in data['cases']))
    def test_finished_trial_is_committed_and_never_called_twice(self):
        class Fixture:
            simulated=True
            count=0
            def __init__(self,*args,**kwargs):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def execute(self,prompt,repo,timeout,log_dir,**kwargs):
                Fixture.count+=1
                oracle=Path(__file__).parents[1]/'evaluation/general/oracle_desk.py'
                (repo/'desk.py').write_text(oracle.read_text())
                return AgentResult(0,'fixture only',.001,{'input_tokens':10,'output_tokens':1,'cached_input_tokens':0},simulated=True,usage_complete=True)
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'campaign'
            with patch('evaluation.general.preflight.run',return_value={'fixture':True}):manifest=plan(root,repeats=1)
            manifest['order']=manifest['order'][:1];(root/'manifest.json').write_text(json.dumps(manifest))
            (root/'preregistered-protocol.json').write_text(json.dumps(manifest))
            record=run_next(root,live=True,adapter_factory=Fixture)
            self.assertTrue(record['artifact_success'])
            self.assertTrue(record['simulated'])
            self.assertIsNone(run_next(root,live=True,adapter_factory=Fixture))
            self.assertEqual(Fixture.count,1)


if __name__=='__main__':unittest.main()
