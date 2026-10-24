import importlib.util, json, subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('audit_110',ROOT/'tools/audit_skill110.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
REPORT=ROOT/'reports/skill-110-2026-10-23.json'
class Skill110PromotionTests(unittest.TestCase):
 def test_report_evidence_and_target(self):
  result=audit.audit(REPORT,ROOT/'reports/skill-110-evidence.zip')
  self.assertTrue(result['promotable'])
  self.assertEqual(result['summary']['totals']['current']['raw_tokens'],209047)
  self.assertLess(result['uncached_change_vs_19_pct'],-12)
 def test_active_default_is_112_and_19_control_remains_historical(self):
  policy=json.loads((ROOT/'PORTABLE_SKILL.json').read_text())
  self.assertEqual(policy['active_native_workflow']['version'],'1.12.5')
  self.assertEqual(json.loads((ROOT/'reports/skill-190-2026-10-23.json').read_text())['skill_version'],'1.9.0')
  run=subprocess.run([sys.executable,str(ROOT/'install.py'),'--host','generic','--dry-run'],capture_output=True,text=True)
  self.assertEqual(run.returncode,0,run.stderr)
  self.assertEqual(json.loads(run.stdout)['skill_version'],'1.12.5')
if __name__=='__main__':unittest.main()
