"""Offline oracle and metric validation; never a claim of agent effectiveness."""
import unittest
from evaluation.ambitious.preflight import run
from evaluation.ambitious.report import calculate


def row(mode,success,seconds=10,repeat=0,case='x'):
    return {'case':case,'mode':mode,'repeat':repeat,'success':success,'artifact_success':success,'normal_exit':True,'seconds':seconds,
    'usage':{'total_tokens':100,'cached_input_tokens':20,'usage_complete':True},'judgments':[{'passed':success}],
    'calls':[{'result':{'telemetry':{'model':{'model':'test'}}}}],'models':['test']}

def protocol(order,cases=['x'],repeats=1):return {'order':order,'cases':cases,'repeats':repeats,'model':'test'}


class AmbitiousEvaluationTests(unittest.TestCase):
    def test_complete_references_pass_and_isolated_faults_are_rejected(self):
        data=run()
        self.assertEqual(set(data),{'flowdesk','stockroom','runforge'})
        self.assertTrue(all(v['reference_groups_passed']==26 and v['initial_groups_failed']==2 for v in data.values()))
        self.assertEqual(sum(len(v['isolated_faults'])for v in data.values()),21)

    def test_savings_without_additional_goals_never_pass_primary(self):
        rows=[row('direct',True,100),row('goalpilot',True,10)];r=calculate(rows,protocol(rows))
        self.assertFalse(r['primary_completion_advantage_observed']);self.assertEqual(r['quality_wins'],0)

    def test_two_additional_goals_and_no_regressions_meet_practical_criterion(self):
        rows=[row(mode,mode=='goalpilot',repeat=i)for i in range(2)for mode in('direct','goalpilot')]
        r=calculate(rows,protocol(rows,repeats=2));self.assertTrue(r['primary_completion_advantage_observed'])
        self.assertEqual(r['groups']['direct']['seconds'],20);self.assertIsNone(r['groups']['direct']['seconds_per_completed_goal']);self.assertEqual(r['paired_one_sided_p_if_independent'],.25)

    def test_paired_regression_or_missing_model_prevents_positive_claim(self):
        rows=[row(mode,mode=='goalpilot',repeat=i)for i in range(3)for mode in('direct','goalpilot')]
        rows.extend([row('direct',True,repeat=3),row('goalpilot',False,repeat=3)])
        self.assertFalse(calculate(rows,protocol(rows,repeats=4))['primary_completion_advantage_observed'])
        rows=rows[:6];rows[0]['calls'][0]['result']['telemetry']={}
        self.assertFalse(calculate(rows,protocol(rows,repeats=3))['primary_completion_advantage_observed'])

    def test_partial_usage_blocks_complete_token_savings(self):
        rows=[row('direct',True),row('goalpilot',True)];rows[1]['usage']['usage_complete']=False
        r=calculate(rows,protocol(rows));self.assertIsNone(r['savings_percent']['reported_tokens']);self.assertIsNone(r['savings_percent']['uncached_input_plus_output'])
