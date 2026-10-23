"""The promoted default must match full-caller evidence, not a self-reported label."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('skill_efficiency_audit',ROOT/'tools/audit_skill_efficiency.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class SkillEfficiencyEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='goalpilot-efficiency-proof-')
        cls.folder=Path(cls.temp.name)
        with zipfile.ZipFile(ROOT/'reports/portable-skill-170-r2-2026-10-23.zip')as archive:
            archive.extractall(cls.folder)
        cls.addClassCleanup(cls.temp.cleanup)

    def test_frozen_service_base_is_the_complete_measured_candidate(self):
        result=audit.analyze(self.folder)
        self.assertTrue(result['promotable'])
        self.assertEqual(result['matched_pairs'],20)
        self.assertEqual(result['independent_replay']['recorded_replays'],40)
        self.assertTrue(result['independent_replay']['all_consistent'])
        self.assertEqual(result['primary']['new']['verified_goals'],20)
        policy=json.loads((ROOT/'PORTABLE_SKILL.json').read_text())
        for name in policy['measured_files']:
            expected=self.folder/'candidate-SKILL.md'if name=='SKILL.md'else self.folder/'source/skills/goalpilot-016'/name
            with self.subTest(file=name):
                self.assertEqual(audit.sha(ROOT/policy['bundle']/name),audit.sha(expected))

    def test_provider_tokens_cannot_be_relabelled(self):
        path=next((self.folder/'trials').glob('*/result.json'));original=path.read_bytes()
        row=json.loads(original);row['usage']['uncached_tokens']-=1
        try:
            path.write_text(json.dumps(row))
            with self.assertRaisesRegex(ValueError,'Uncached tokens do not reconcile'):
                audit.analyze(self.folder)
        finally:path.write_bytes(original)

    def test_self_consistent_unapproved_code_cannot_execute(self):
        path=self.folder/'source/install.py';original=path.read_bytes()
        protocol=self.folder/'protocol.json';old_protocol=protocol.read_bytes()
        try:
            path.write_bytes(original+b"\nraise AssertionError('Untrusted archived code executed')\n")
            value=json.loads(old_protocol)
            value['source_hashes']['install.py']=hashlib.sha256(path.read_bytes()).hexdigest()
            protocol.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'Unapproved archived executable source'):
                audit.analyze(self.folder)
        finally:
            path.write_bytes(original);protocol.write_bytes(old_protocol)

    def test_a_missing_registered_attempt_prevents_promotion(self):
        protocol=json.loads((self.folder/'protocol.json').read_text())
        item=protocol['order'][-1];path=self.folder/'trials'/(item['case']+'-'+item['arms'][-1])/'result.json'
        original=path.read_bytes()
        try:
            path.unlink()
            with self.assertRaisesRegex(ValueError,'Independent replay cases differ'):
                audit.analyze(self.folder)
        finally:path.write_bytes(original)
