"""The active default must have its own evidence, separately from frozen 1.8."""
import copy,hashlib,importlib.util,json
from pathlib import Path
import subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('audit_190',ROOT/'tools/audit_skill190.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
REPORT=ROOT/'reports/skill-190-2026-10-23.json'
class Promotion190(unittest.TestCase):
 def test_active_default_is_source_bound_and_old_controls_remain_separate(self):
  result=audit.analyze(REPORT,ROOT/'reports/skill-190-evidence.zip');self.assertTrue(result['promotable'])
  policy=json.loads((ROOT/'PORTABLE_SKILL.json').read_text());active=policy['active_native_workflow']
  self.assertEqual(active['version'],'1.10.0');self.assertEqual(policy['native_workflow']['version'],'1.8.0')
  self.assertNotEqual(active['benchmark_sha256'],hashlib.sha256(REPORT.read_bytes()).hexdigest());self.assertEqual(json.loads(REPORT.read_text())['skill_version'],'1.9.0')
  result=subprocess.run([sys.executable,str(ROOT/'install.py'),'--host','generic','--dry-run'],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['skill_version'],'1.10.0')
 def test_gains_and_installed_payloads_cannot_be_relabelled(self):
  for mutate in (lambda d:d['summary']['totals']['current'].__setitem__('raw_tokens',1),lambda d:d['install_parity']['codex']['deployed'].clear()):
   d=json.loads(REPORT.read_text());mutate(d)
   with tempfile.TemporaryDirectory()as tmp:
    p=Path(tmp)/'report.json';p.write_text(json.dumps(d))
    with self.assertRaises(ValueError):audit.analyze(p)
 def test_runtime_source_cannot_change_after_measurement(self):
  d=json.loads(REPORT.read_text());d['source_files']['integrations/native/native.py']='0'*64
  with tempfile.TemporaryDirectory()as tmp:
   p=Path(tmp)/'report.json';p.write_text(json.dumps(d))
   with self.assertRaisesRegex(ValueError,'promoted source'):audit.analyze(p)
