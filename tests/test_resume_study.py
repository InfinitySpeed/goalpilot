import unittest
from goalpilot.engine import token_totals
from tools.resume_study import summarize


class ResumeStudyTests(unittest.TestCase):
    def manifest(self):
        results=[]
        for i in range(4):
            for mode in ('direct','goalpilot'):
                remote=mode=='direct' or i==3
                calls=[{'usage':{'input_tokens':100,'output_tokens':10,'cached_input_tokens':50},
                        'usage_complete':True,'telemetry':{'model':{'model':'gpt-6.1-sol'}}}] if remote else []
                results.append({'mode':mode,'external_success':True,'status':'scope_passed',
                    'seconds':10 if remote else .1,'new_agent_turns':len(calls),
                    'usage':token_totals([{'result':x} for x in calls]),'calls':calls})
        return {'results':results}

    def test_no_remote_call_is_known_zero_and_can_be_compared_to_real_calls(self):
        report=summarize(self.manifest())
        self.assertEqual(report['groups']['direct']['agent_turns'],4)
        self.assertEqual(report['groups']['goalpilot']['agent_turns'],1)
        self.assertEqual(report['reported_token_reduction_percent'],75)
        self.assertTrue(report['primary_threshold_met'])

    def test_partial_remote_usage_or_unverified_scope_prevents_claim(self):
        manifest=self.manifest()
        manifest['results'][0]['usage']['usage_complete']=False
        self.assertFalse(summarize(manifest)['primary_threshold_met'])
        manifest=self.manifest()
        manifest['results'][-1]['status']='budget_exhausted'
        self.assertFalse(summarize(manifest)['primary_threshold_met'])


if __name__=='__main__':unittest.main()
