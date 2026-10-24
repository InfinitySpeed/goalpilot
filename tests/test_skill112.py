import json, subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import audit_native_task_domination as audit
class Skill112PromotionTests(unittest.TestCase):
 def test_active_candidate_and_recomputed_gates(self):
  result=audit.audit(ROOT); self.assertTrue(result['promotable'])
  policy=json.loads((ROOT/'PORTABLE_SKILL.json').read_text());self.assertEqual(policy['active_native_workflow']['version'],'1.12.5')
  self.assertEqual(policy['native_workflow']['version'],'1.8.0')
 def test_stable_installer_selects_promoted_skill(self):
  run=subprocess.run([sys.executable,str(ROOT/'install.py'),'--host','generic','--dry-run'],capture_output=True,text=True)
  self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(json.loads(run.stdout)['skill_version'],'1.12.5')
if __name__=='__main__':unittest.main()
