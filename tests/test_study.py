import copy
import unittest

from evaluation.dossier_study import summarize
from evaluation.reference_oracles import preflight
from evaluation.reference_oracles_v21 import preflight as preflight_v21


class StudyTests(unittest.TestCase):
    def manifest(self):
        results=[]
        for repeat in (1,2):
            for mode in ('direct','goalpilot'):
                results.append({'case':'case','repeat':repeat,'mode':mode,
                    'seconds':100 if mode=='direct' else 80,
                    'external_success':True,'usage_complete':True,'command_count':2,
                    'models':['same-model'],'agent_turns':1,
                    'usage':{'input_tokens':1000,'output_tokens':100,'cached_input_tokens':500}})
        return {'cases':[{'name':'case'}],'stage':'validation','repeats':2,
                'success_rule':'fixed','results':results}

    def test_complete_paired_speed_gain_passes(self):
        summary=summarize(self.manifest())
        self.assertTrue(summary['primary_threshold_met'])
        self.assertAlmostEqual(summary['time_reduction_percent'],20)
        self.assertEqual(summary['paired_cases'],2)
        self.assertEqual(summary['unique_projects'],1)

    def test_partial_usage_or_missing_repeat_cannot_prove_gain(self):
        for variant in ('partial','missing','model','quality'):
            manifest=self.manifest()
            if variant=='partial':manifest['results'][0]['usage_complete']=False
            if variant=='missing':manifest['results'].pop()
            if variant=='model':manifest['results'][0]['models']=['other-model']
            if variant=='quality':manifest['results'][0]['external_success']=False
            self.assertFalse(summarize(manifest)['primary_threshold_met'],variant)

    def test_cached_token_reduction_alone_does_not_meet_primary(self):
        manifest=self.manifest()
        for item in manifest['results']:
            item['seconds']=100
            item['usage']={'input_tokens':1000,'output_tokens':100,'cached_input_tokens':900}
            if item['mode']=='goalpilot':
                item['usage']={'input_tokens':500,'output_tokens':100,'cached_input_tokens':0}
        summary=summarize(manifest)
        self.assertGreater(summary['reported_token_reduction_percent'],40)
        self.assertLess(summary['non_cached_token_reduction_percent'],0)
        self.assertFalse(summary['primary_threshold_met'])

    def test_hidden_verifiers_accept_independent_references_and_reject_stubs(self):
        result=preflight()
        self.assertEqual(len(result['cases']),3)
        self.assertTrue(all(x['unfinished_seed_rejected'] for x in result['cases']))
        self.assertEqual(sum(x['reference_checks_passed'] for x in result['cases']),8)

    def test_fresh_verifiers_accept_references_and_reject_stubs(self):
        result=preflight_v21()
        self.assertEqual(len(result['cases']),3)
        self.assertTrue(all(x['unfinished_seed_rejected'] for x in result['cases']))
        self.assertEqual(sum(x['reference_checks_passed'] for x in result['cases']),6)


if __name__=='__main__':unittest.main()
