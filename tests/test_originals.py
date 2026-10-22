import json
from pathlib import Path
import tempfile
import unittest


class OriginalSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.repo=self.root/'repo';self.repo.mkdir()

    def test_original_bytes_are_retained_and_credentials_and_links_excluded(self):
        from goalpilot.originals import capture
        (self.repo/'USER_NOTES.txt').write_text('original café')
        (self.repo/'inventory.json').write_text('{"user":"original"}')
        (self.repo/'.env').write_text('DO NOT COPY')
        (self.repo/'secret.json').write_text('DO NOT COPY')
        (self.repo/'link').symlink_to('/etc/passwd')
        snapshot=capture(self.repo,self.root/'original-tree')
        (self.repo/'USER_NOTES.txt').write_text('changed')
        self.assertEqual((self.root/'original-tree/USER_NOTES.txt').read_text(),'original café')
        self.assertEqual((self.root/'original-tree/inventory.json').read_text(),'{"user":"original"}')
        self.assertEqual({x['path'] for x in snapshot['files']},{'USER_NOTES.txt','inventory.json'})
        self.assertTrue((self.root/'original-inventory.json').exists())

    def test_limits_are_explicit_and_oversize_files_are_not_truncated_as_evidence(self):
        from goalpilot.originals import capture
        (self.repo/'large.db').write_bytes(b'x'*100)
        (self.repo/'small.txt').write_text('small')
        snapshot=capture(self.repo,self.root/'original-tree',max_file_bytes=50)
        self.assertFalse(snapshot['within_limits'])
        self.assertIn('large.db',snapshot['omitted'])
        self.assertFalse((self.root/'original-tree/large.db').exists())

    def test_ordinary_metadata_captured_but_hidden_credentials_still_excluded(self):
        from goalpilot.originals import capture, PROJECT_METADATA
        for name in PROJECT_METADATA:
            (self.repo/name).write_text('project metadata\n')
        for name in ('.env', '.npmrc', '.auth.json', '.gitignore.secret'):
            (self.repo/name).write_text('DO NOT COPY')
        (self.repo/'.git').mkdir()
        (self.repo/'.git/config').write_text('ignored VCS metadata')
        snapshot=capture(self.repo,self.root/'original-tree')
        self.assertEqual({x['path']for x in snapshot['files']},PROJECT_METADATA)
        self.assertEqual(set(snapshot['omitted']),{'.env','.npmrc','.auth.json','.gitignore.secret'})
        self.assertTrue(snapshot['within_limits'])

    def test_metadata_symlink_is_never_copied(self):
        from goalpilot.originals import capture
        (self.repo/'.gitignore').symlink_to('/etc/passwd')
        snapshot=capture(self.repo,self.root/'original-tree')
        self.assertEqual(snapshot['files'],[])
        self.assertIn('.gitignore',snapshot['omitted'])

    def test_general_evidence_limits_do_not_prevent_closure(self):
        from goalpilot.finish import run_finish
        from tests.test_finish import Auditor,Builder,result
        class LimitsAuditor(Auditor):
            def execute(self,*args,**kwargs):
                r=super().execute(*args,**kwargs)
                data=json.loads(r.message);data['limitations']=['Cannot prove every future power loss']
                r.message=json.dumps(data);return r
        state=run_finish('Deliver 42',self.repo,self.root/'run',wall_seconds=30,adapter=Builder(),auditor=LimitsAuditor())
        self.assertEqual(state['status'],'scope_passed')
        self.assertIn('Cannot prove every future power loss',state['contract']['limitations'])
        self.assertEqual(state['contract']['unverified'],[])
        flow=json.loads((self.root/'run/finish-run.json').read_text())
        self.assertIn('original_snapshot',flow)

    def test_live_status_advances_time_without_remote_calls_or_source_dump(self):
        from goalpilot.view import status
        from unittest.mock import patch
        run=self.root/'run';run.mkdir()
        (run/'finish-run.json').write_text(json.dumps({'config':{'goal':'goal','budget':{'max_calls':5,'wall_seconds':100}},
            'phase':'build','status':'running','active_seconds':2,'calls':[{'strategy':'build'}],
            'original_contract':'DO NOT DUMP','pending':{'started_active_seconds':2,'started_at':1000,'reserved_seconds':55,'index':0}}))
        with patch('goalpilot.view.time.time',return_value=1010):out=status(run)
        self.assertEqual(out['active_seconds_estimate'],12)
        self.assertEqual(out['remaining_seconds_estimate'],88)
        self.assertFalse(out['usage']['usage_complete'])
        self.assertNotIn('DO NOT DUMP',json.dumps(out))


if __name__=='__main__':unittest.main()
