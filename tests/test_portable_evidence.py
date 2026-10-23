"""Offline release evidence: complete meters, immutable sources and corruption rejection."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('portable_release_audit',ROOT/'tools/audit_portable_invocation.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class PortableEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='goalpilot-evidence-')
        cls.folder=Path(cls.temp.name)
        with zipfile.ZipFile(ROOT/'reports/portable-skill-170-2026-10-23.zip')as archive:
            archive.extractall(cls.folder)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_full_provider_evidence_reconciles(self):
        result=audit.analyze(self.folder)
        self.assertTrue(result['promotable'])
        self.assertEqual(result['matched_pairs'],20)
        self.assertEqual(result['primary']['new']['raw'],1417187)
        self.assertEqual(result['completion']['old']['verified_goals'],20)
        self.assertEqual(result['completion']['new']['verified_goals'],20)
        self.assertEqual(result['completion']['old']['exact_goal_files'],15)

    def test_one_reported_token_cannot_be_added(self):
        path=next((self.folder/'trials').glob('*/result.json'));original=path.read_bytes()
        row=json.loads(original);row['usage']['total_tokens']+=1
        try:
            path.write_text(json.dumps(row))
            with self.assertRaisesRegex(ValueError,'Raw tokens do not reconcile'):audit.analyze(self.folder)
        finally:path.write_bytes(original)

    def test_incomplete_benchmark_cannot_promote(self):
        path=next((self.folder/'trials').glob('*/result.json'));original=path.read_bytes()
        try:
            path.unlink();result=audit.analyze(self.folder)
            self.assertFalse(result['promotable'])
            self.assertEqual(result['recorded_calls'],39)
            self.assertEqual(result['matched_pairs'],19)
        finally:path.write_bytes(original)

    def test_frozen_service_base_is_identical_to_measured_behavior_files(self):
        policy=json.loads((ROOT/'PORTABLE_SKILL.json').read_text())
        self.assertEqual(policy['status'],'promoted')
        self.assertEqual(policy['default'],'skills/goalpilot-016')
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        self.assertEqual(sha(ROOT/policy['evidence_archive']),policy['evidence_sha256'])
        for name,digest in policy['measured_files'].items():
            self.assertEqual(sha(ROOT/policy['bundle']/name),digest,name)
        self.assertEqual(audit.hashes(self.folder/'source/skills/goalpilot/runtime/goalpilot'),audit.hashes(ROOT/'skills/goalpilot/runtime/goalpilot'))
