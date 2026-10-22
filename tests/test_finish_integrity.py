import hashlib
from pathlib import Path
import sys
import tempfile
import time
import unittest
from goalpilot.engine import verify
from goalpilot.finish import run_finish
from goalpilot.model import ContractError
from tests.test_finish import Builder,Auditor


class IntegrityTests(unittest.TestCase):
    def test_probe_rewriting_itself_cannot_validate_its_changed_result(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);repo=root/'repo';repo.mkdir();probe=root/'probe.py'
            probe.write_text("from pathlib import Path\nPath(__file__).write_text('assert True')\nassert True\n")
            contract={'repo':str(repo),'checks':[{'id':'x','command':[sys.executable,str(probe)]}],
                      'artifacts':[{'path':str(probe),'sha256':hashlib.sha256(probe.read_bytes()).hexdigest()}]}
            checks=verify(contract,time.monotonic()+5,root/'logs')
            self.assertFalse(checks[0]['passed'])
            self.assertTrue(checks[0]['infrastructure_error'])

    def test_changed_original_evidence_blocks_audit(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);repo=root/'repo';repo.mkdir();run=root/'run'
            (repo/'USER_NOTES.txt').write_text('original')
            class TamperingBuilder(Builder):
                def execute(self,*args,**kwargs):
                    (run/'original-tree/USER_NOTES.txt').write_text('tampered')
                    return super().execute(*args,**kwargs)
            auditor=Auditor()
            with self.assertRaisesRegex(ContractError,'Original file evidence changed'):
                run_finish('Deliver 42',repo,run,adapter=TamperingBuilder(),auditor=auditor)
            self.assertEqual(auditor.calls,0)


if __name__=='__main__':unittest.main()
