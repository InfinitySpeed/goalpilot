"""Installer safeguards: source preservation and truthful selected-profile readiness."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]


class InstallProfiles(unittest.TestCase):
    def invoke(self,*args,root=ROOT):
        return subprocess.run([sys.executable,str(root/'install.py'),*map(str,args)],capture_output=True,text=True,timeout=30)

    def test_all_source_profiles_and_descendants_are_protected(self):
        spec=importlib.util.spec_from_file_location('profile_guard',ROOT/'install.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for directory in ('skills/goalpilot','skills/goalpilot-016','benchmarks','goalpilot'):
            for target in (ROOT/directory,ROOT/directory/'uncreated-install-target'):
                with self.subTest(target=target),self.assertRaisesRegex(ValueError,'protected repository source'):
                    module.preflight(target)
        for profile in ('stable','legacy','candidate'):
            result=self.invoke('--profile',profile,'--host','codex','--target',ROOT/'skills/goalpilot','--dry-run')
            self.assertNotEqual(result.returncode,0,result.stdout)
            self.assertIn('protected repository source',result.stderr)

    def test_doctor_rejects_another_valid_profile(self):
        with tempfile.TemporaryDirectory()as tmp:
            target=Path(tmp)/'skill'
            installed=self.invoke('--profile','legacy','--host','codex','--target',target)
            self.assertEqual(installed.returncode,0,installed.stderr)
            self.assertEqual((target/'LICENSE').read_bytes(),(ROOT/'LICENSE').read_bytes())
            legacy=self.invoke('--profile','legacy','--host','codex','--target',target,'--doctor')
            stable=self.invoke('--profile','stable','--host','codex','--target',target,'--doctor')
            self.assertEqual(legacy.returncode,0,legacy.stderr)
            self.assertNotEqual(stable.returncode,0)
            self.assertFalse(json.loads(stable.stdout)['ready'])
            self.assertIn('requested profile',json.loads(stable.stdout)['checks'][0]['error'])

    def test_stable_rejects_a_changed_self_consistent_bundle(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp)/'source';root.mkdir()
            shutil.copy2(ROOT/'install.py',root/'install.py')
            shutil.copy2(ROOT/'PORTABLE_SKILL.json',root/'PORTABLE_SKILL.json')
            skill=root/'skills/goalpilot-016'
            shutil.copytree(ROOT/'skills/goalpilot-016',skill,ignore=shutil.ignore_patterns('__pycache__'))
            instructions=skill/'SKILL.md';instructions.write_text(instructions.read_text()+'\nLocal experiment\n')
            manifest=json.loads((skill/'MANIFEST.json').read_text())
            manifest['files']['SKILL.md']=hashlib.sha256(instructions.read_bytes()).hexdigest()
            (skill/'MANIFEST.json').write_text(json.dumps(manifest))
            flags=('--host','codex','--target',Path(tmp)/'target','--dry-run')
            stable=self.invoke(*flags,root=root)
            self.assertNotEqual(stable.returncode,0)
            self.assertIn('differs from the promoted measurement',stable.stderr)
            candidate=self.invoke('--profile','candidate',*flags,root=root)
            self.assertEqual(candidate.returncode,0,candidate.stderr)
            self.assertEqual(json.loads(candidate.stdout)['selected_profile'],'candidate')

    def test_invalid_promotion_metadata_has_a_clean_error(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);shutil.copy2(ROOT/'install.py',root/'install.py')
            (root/'PORTABLE_SKILL.json').write_text('{broken')
            result=self.invoke('--dry-run',root=root)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Installation refused',result.stderr)
            self.assertNotIn('Traceback',result.stderr)

    def test_doctor_rejects_changed_instructions_with_the_same_version(self):
        with tempfile.TemporaryDirectory()as tmp:
            target=Path(tmp)/'skill'
            installed=self.invoke('--host','codex','--target',target)
            self.assertEqual(installed.returncode,0,installed.stderr)
            manifest_path=target/'MANIFEST.json';original_manifest=manifest_path.read_bytes()
            instructions=target/'SKILL.md';original=instructions.read_bytes()
            instructions.write_bytes(original+b'\nDifferent execution instructions\n')
            manifest=json.loads(original_manifest)
            manifest['files']['SKILL.md']=hashlib.sha256(instructions.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            report=self.invoke('--host','codex','--target',target,'--doctor')
            self.assertNotEqual(report.returncode,0)
            self.assertIn('Installed behavior differs',json.loads(report.stdout)['checks'][0]['error'])
            # A recorded interpreter-version string may predate an in-place Python update.
            instructions.write_bytes(original);manifest=json.loads(original_manifest)
            runtime_path=target/'RUNTIME.json';runtime=json.loads(runtime_path.read_text())
            runtime['python_version']='3.11.0'
            runtime_path.write_text(json.dumps(runtime,indent=2)+'\n')
            manifest['files']['RUNTIME.json']=hashlib.sha256(runtime_path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            report=self.invoke('--host','codex','--target',target,'--doctor')
            self.assertEqual(report.returncode,0,report.stderr+report.stdout)

    def test_downloadable_package_carries_a_verified_license(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp)
            shutil.copytree(ROOT/'skills/goalpilot-016',root/'skills/goalpilot-016',ignore=shutil.ignore_patterns('__pycache__'))
            for name in ('PORTABLE_SKILL.json','PROMOTED_ENGINE.json','LICENSE'):
                shutil.copy2(ROOT/name,root/name)
            spec=importlib.util.spec_from_file_location('licensed_package_builder',ROOT/'tools/build_portable_skill.py')
            builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
            receipt=builder.build(root)
            self.assertEqual(receipt['model_calls'],0)
            with zipfile.ZipFile(root/'dist/goalpilot-skill-1.7.0.zip')as archive:
                license_bytes=archive.read('goalpilot/LICENSE')
                self.assertEqual(license_bytes,(ROOT/'LICENSE').read_bytes())
                manifest=json.loads(archive.read('goalpilot/MANIFEST.json'))
                self.assertEqual(manifest['files']['LICENSE'],hashlib.sha256(license_bytes).hexdigest())
                self.assertEqual(manifest['engine']['version'],'0.16.0')
