"""A favorable aggregate must not conceal task regressions or corrupt counters."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('extension_audit', ROOT / 'tools/audit_portability_extension.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def outcomes():
    return [{'case': case, 'arm': arm, 'correct': True, 'certified': None if arm == 'native' else True,
             'goal_preserved': None if arm == 'native' else True, 'seconds': 1,
             'usage': {'input_tokens': 90, 'output_tokens': 10, 'cached_input_tokens': 60,
                       'total_tokens': 100, 'uncached_tokens': 40, 'usage_complete': True}}
            for case in ('a', 'b', 'c', 'd') for arm in AUDIT.ARMS]


class ExtensionEvidence(unittest.TestCase):
    def test_aggregate_gain_cannot_hide_individual_regression(self):
        rows = outcomes()
        for row in rows:
            if row['arm'] == 'current':
                factor = 2 if row['case'] == 'a' else .5
                row['usage'] = {k: int(v * factor) if type(v) is int else v for k, v in row['usage'].items()}
        result = AUDIT.summarize(rows)
        self.assertTrue(result['gates']['aggregate_tokens_no_regression'])
        self.assertFalse(result['gates']['uniform_per_case_no_regression'])
        self.assertEqual({r['case'] for r in result['per_case_regressions']}, {'a'})
        self.assertFalse(result['gates']['universal_claim_established'])

    def test_missing_outcomes_incomplete_usage_and_bad_totals_are_rejected(self):
        rows = outcomes()
        with self.assertRaises(ValueError):
            AUDIT.summarize(rows[:-1])
        for key, value in (('usage_complete', False), ('cached_input_tokens', 1000), ('total_tokens', 99)):
            changed = copy.deepcopy(rows)
            changed[0]['usage'][key] = value
            with self.assertRaises(ValueError):
                AUDIT.summarize(changed)

    def test_claims_cannot_disagree_with_measured_outcomes(self):
        rows = outcomes()
        report = {'schema_version': 1, 'rows': rows, 'summary': AUDIT.summarize(rows)}
        AUDIT.audit(report)
        report['summary']['gates']['universal_claim_established'] = True
        with self.assertRaises(ValueError):
            AUDIT.audit(report)


if __name__ == '__main__':
    unittest.main()
