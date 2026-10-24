import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/native-only-benchmark-2026-10-24.json'
ARCHIVE = ROOT / 'reports/native-only-evidence-2026-10-24.zip'

class Skill114Promotion(unittest.TestCase):
    def test_native_only_evidence_and_source_are_bound(self):
        policy = json.loads((ROOT / 'PORTABLE_SKILL.json').read_text())
        active = policy['active_native_workflow']
        report = json.loads(REPORT.read_text())
        self.assertEqual(active['version'], '1.14.0')
        self.assertEqual(active['status'], 'promoted')
        self.assertIn('Codex native', report['scope'])
        self.assertEqual(report['native_only_summary']['matched_pairs'], 8)
        self.assertEqual(report['native_only_summary']['hidden_tests']['codex_native'], {'passed': 14, 'total': 21})
        self.assertEqual(report['native_only_summary']['hidden_tests']['goalpilot'], {'passed': 21, 'total': 21})
        self.assertEqual(active['benchmark_sha256'], hashlib.sha256(REPORT.read_bytes()).hexdigest())
        self.assertEqual(active['evidence_sha256'], hashlib.sha256(ARCHIVE.read_bytes()).hexdigest())
        for name, digest in active['source_files'].items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest)

    def test_stable_installer_selects_114(self):
        run = subprocess.run([sys.executable, str(ROOT / 'install.py'), '--host', 'generic', '--dry-run'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['skill_version'], '1.14.0')

if __name__ == '__main__':
    unittest.main()
