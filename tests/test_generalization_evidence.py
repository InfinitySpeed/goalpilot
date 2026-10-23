"""The generalized default needs its own complete, source-pinned caller evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('generalization_audit',ROOT/'tools/audit_generalization.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
REPORT=ROOT/'reports/native-generalization-2026-10-23.json'

class GeneralizationEvidence(unittest.TestCase):
    def test_default_has_all_registered_outcomes_and_exact_current_sources(self):
        result=audit.analyze(REPORT);self.assertTrue(result['promotable'])
        self.assertEqual(result['scores']['new']['certified'],8)
        policy=json.loads((ROOT/'PORTABLE_SKILL.json').read_text())['native_workflow']
        self.assertEqual(policy['status'],'promoted')
        self.assertEqual(policy['benchmark_sha256'],hashlib.sha256(REPORT.read_bytes()).hexdigest())
        report=json.loads(REPORT.read_text())
        self.assertEqual(report['independent_replay']['replayed'],45)
        self.assertTrue(report['independent_replay']['consistent'])
        self.assertEqual(policy['source_files'],report['source_files'])

    def tampered(self,change,pattern):
        data=json.loads(REPORT.read_text());change(data)
        with tempfile.TemporaryDirectory()as tmp:
            path=Path(tmp)/'report.json';path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,pattern):audit.analyze(path)

    def test_a_provider_counter_cannot_be_silently_relabelled(self):
        self.tampered(lambda r:r['trials'][0]['tokens'].__setitem__(0,r['trials'][0]['tokens'][0]+1),'Provider meter changed')

    def test_missing_attempt_or_source_identity_prevents_promotion(self):
        self.tampered(lambda r:r['trials'].pop(),'All24 registered')
        self.tampered(lambda r:r['source_files'].clear(),'Complete measured source')
