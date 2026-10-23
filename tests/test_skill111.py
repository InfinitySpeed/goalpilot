import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit_skill111', ROOT / 'tools/audit_skill111.py')
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)

class Skill111PromotionTests(unittest.TestCase):
    def test_source_bound_repeated_promotion_gates(self):
        data = audit_module.audit()
        self.assertTrue(data['promotable'])
        self.assertLess(data['candidate_change_pct_vs_1_9']['uncached_input_plus_output'], -20)
        self.assertLess(data['candidate_change_pct_vs_1_10']['uncached_input_plus_output'], -15)
        self.assertLessEqual(data['candidate_change_pct_vs_1_9']['seconds'], 3)
        self.assertFalse(data['quota_savings_claimed'])

if __name__ == '__main__':
    unittest.main()
