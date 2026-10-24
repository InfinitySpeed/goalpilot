import importlib.util, json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('audit_skill112',ROOT/'tools/audit_skill112.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
class Skill112HistoricalEvidence(unittest.TestCase):
 def test_archived_fast_path_evidence_remains_valid_without_being_the_current_control(self):
  result=audit.audit()
  active=json.loads((ROOT/'PORTABLE_SKILL.json').read_text())['active_native_workflow']
  self.assertTrue(result['historical_evidence_valid'])
  self.assertEqual(result['version'],'1.12.0')
  self.assertEqual(active['version'],'1.14.0')
if __name__=='__main__':unittest.main()
