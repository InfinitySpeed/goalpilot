"""Compatibility evidence must distinguish unsupported tools from passing checks."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('portability_check', ROOT / 'tools/check_portability.py')
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class PortabilityEvidence(unittest.TestCase):
    def test_unrelated_go_program_is_not_compiler_support(self):
        with patch.object(TOOL.shutil, 'which', return_value='/usr/bin/go'), patch.object(TOOL, 'execute', return_value=subprocess.CompletedProcess([], 0, 'Go board game', '')):
            self.assertFalse(TOOL.capability(['go', 'version'])['ready'])

    def test_missing_runtime_is_explicitly_unavailable(self):
        with patch.object(TOOL.shutil, 'which', return_value=None):
            result = TOOL.capability(['not-installed', '--version'])
        self.assertFalse(result['ready'])
        self.assertIn('missing', result['reason'])

    def test_real_install_rejects_wrong_answer_and_invalidates_stale_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'report.json'
            result = subprocess.run([sys.executable, str(ROOT / 'tools/check_portability.py'), '--hosts', 'generic', '--stacks', 'python', '--require-all', '--output', str(output)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual((data['passed'], data['failed'], data['unsupported']), (1, 0, 0))
            self.assertTrue(all(data['rows'][0]['checks'].values()))
            self.assertEqual(data['live_model_calls'], 0)


if __name__ == '__main__':
    unittest.main()
