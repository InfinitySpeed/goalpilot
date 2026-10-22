"""Prevent false efficacy claims from normalized costs, omissions and missing usage."""
import unittest
from evaluation.triple.report import calculate


def fixture(gp_cost=60):
    m={'cases':['a','b','c'],'repeats':1,'model':'same','resource_threshold_percent':15,'order':list(range(6))}
    rows=[]
    for case in m['cases']:
        for mode in ('direct','goalpilot'):
            success=mode=='goalpilot'or case!='b';cost=100 if mode=='direct'else gp_cost
            rows.append({'mode':mode,'case':case,'repeat':0,'success':success,'seconds':cost,'calls':[{}],
                'usage':{'total_tokens':cost*10,'cached_input_tokens':0,'usage_complete':True},
                'normal_exit':True,'artifact_success':success,'models':['same'],'fatal':False})
    return rows,m


class TripleMetricTests(unittest.TestCase):
    def test_failed_trials_remain_in_cost_per_delivered_goal(self):
        rows,m=fixture();r=calculate(rows,m)
        self.assertEqual(r['groups']['direct']['seconds_per_completed_goal'],150)
        self.assertEqual(r['groups']['goalpilot']['seconds_per_completed_goal'],60)
        self.assertEqual(r['groups']['direct']['false_completion'],1)
        self.assertTrue(r['joint_preregistered_criterion_met'])

    def test_normalized_saving_is_not_an_absolute_saving(self):
        rows,m=fixture(110);r=calculate(rows,m)
        self.assertLess(r['savings_percent']['seconds'],0)
        self.assertGreater(r['savings_percent']['seconds_per_completed_goal'],15)
        self.assertTrue(r['joint_preregistered_criterion_met'])

    def test_partial_usage_prevents_token_proof(self):
        rows,m=fixture();rows[-1]['usage']['usage_complete']=False;r=calculate(rows,m)
        self.assertIsNone(r['groups']['goalpilot']['tokens_per_completed_goal'])
        self.assertFalse(r['eligible']);self.assertFalse(r['joint_preregistered_criterion_met'])

    def test_incomplete_campaign_cannot_prove_a_joint_gain(self):
        rows,m=fixture();self.assertFalse(calculate(rows[:-1],m)['joint_preregistered_criterion_met'])

    def test_model_mismatch_blocks_claim(self):
        rows,m=fixture();rows[0]['models']=['different'];self.assertFalse(calculate(rows,m)['eligible'])

    def test_a_paired_completion_regression_blocks_joint_claim(self):
        rows,m=fixture()
        for r in rows:
            r['success']=(r['case']=='a')if r['mode']=='direct'else r['case']!='a'
        result=calculate(rows,m)
        self.assertEqual(result['quality_losses'],1);self.assertFalse(result['joint_preregistered_criterion_met'])
