import hashlib,json,sys,tempfile,time,unittest
from pathlib import Path
from goalpilot.engine import verify


class ProbeContextTests(unittest.TestCase):
    def test_frozen_external_probe_imports_public_project_and_still_detects_real_failure(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t);repo=root/'repo';repo.mkdir();probe=root/'external-probe.py'
            (repo/'app.py').write_text('def answer():return 0\n');probe.write_text('from app import answer\nassert answer()==42\n')
            sha=hashlib.sha256(probe.read_bytes()).hexdigest()
            contract={'repo':str(repo),'scope':'inferred','artifacts':[{'path':str(probe),'sha256':sha}],
            'checks':[{'id':'answer','description':'Public answer works','command':[sys.executable,str(probe)]}]}
            first=verify(contract,time.monotonic()+5,root/'first')[0]
            self.assertFalse(first['passed']);self.assertIn('AssertionError',first['output']);self.assertNotIn('ModuleNotFoundError',first['output'])
            (repo/'app.py').write_text('def answer():return 42\n')
            last=verify(contract,time.monotonic()+5,root/'last')[0]
            self.assertTrue(last['passed']);self.assertTrue(last['repository_import_path'])
            self.assertEqual(hashlib.sha256(probe.read_bytes()).hexdigest(),sha)
