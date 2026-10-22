from pathlib import Path
import tempfile,shutil
from .case import materialize
from .judge import evaluate,WORK_GROUPS
from evaluation.triple.cases import reference


def run():
    with tempfile.TemporaryDirectory()as t:
        repo=Path(t)/'repo';materialize(repo);initial=evaluate(repo)
        for name in ('daybook','tablekit','resolver'):(repo/name/'core.py').write_text(reference(name))
        correct=Path(__file__).with_name('reference.py').read_text();(repo/'workbench.py').write_text(correct)
        for p in repo.rglob('__pycache__'):shutil.rmtree(p)
        good=evaluate(repo);assert all(x['passed']for x in good),[x for x in good if not x['passed']]
        mutations=[
            ("if db.execute('select 1 from runs where pipeline=?and revision=?and at=?',(ident,rev,at)).fetchone():continue",'if False:continue'),
            ("db.execute('update pipelines set config=?,revision=revision+1 where id=?'","\n            if old['config']==normalized:return old\n            db.execute('update pipelines set config=?,revision=revision+1 where id=?'"),
            ("converted={'columns':result['columns'],'rows':[[str(x)if type(x)is int else x for x in row]for row in result['rows']]}","converted=result"),
            ('new.append(cursor.lastrowid)',"new.append(cursor.lastrowid);db.commit();db.execute('begin immediate')")]
        sensitivity=[]
        for i,(before,after)in enumerate(mutations):
            assert before in correct
            (repo/'workbench.py').write_text(correct.replace(before,after,1))
            for p in repo.rglob('__pycache__'):shutil.rmtree(p)
            checks=evaluate(repo,groups=['workspace/'+g for g in WORK_GROUPS]);rejected=[x['id']for x in checks if not x['passed']]
            assert rejected,i;sensitivity.append({'fault':i+1,'rejected_by':rejected})
        return {'model_calls':0,'initial_failed_groups':[x['id']for x in initial if not x['passed']],'reference_passed_groups':len(good),'semantic_faults':sensitivity}
