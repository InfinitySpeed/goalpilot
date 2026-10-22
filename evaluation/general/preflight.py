"""Check judge attainability and sensitivity before any live model calls."""
import json
from pathlib import Path
import shutil
import tempfile
from .cases import cases,materialize
from .judge import evaluate


def run():
    findings=[]
    for case in cases():
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);repo=root/'repo';materialize(case,repo)
            unfinished=evaluate(case,repo)
            assert not all(x['passed'] for x in unfinished),case['name']
            oracle=Path(__file__).with_name('oracle_'+case['name']+'.py').read_text()
            (repo/case['entry']).write_text(oracle)
            reference=evaluate(case,repo)
            assert all(x['passed'] for x in reference),[(case['name'],x['id'],x['error']) for x in reference if not x['passed']]
            # Specific semantic faults, rather than just syntax errors or stubs.
            if case['name']=='desk':mutant=oracle.replace('type(priority) is int','isinstance(priority,int)')
            elif case['name']=='queue':mutant=oracle.replace("found['worker']==a.worker","True")
            else:mutant=oracle.replace("assert info['ok'];dest=","dest=")
            assert mutant!=oracle
            (repo/case['entry']).write_text(mutant)
            mutated=evaluate(case,repo)
            rejected=[x['id'] for x in mutated if not x['passed']]
            assert rejected,(case['name'],'semantic mutation escaped')
            findings.append({'case':case['name'],'unfinished_checks_failed':sum(not x['passed'] for x in unfinished),
                'reference_checks_passed':len(reference),'semantic_mutation_rejected_by':rejected})
    return {'kind':'independent_judge_preflight','model_calls':0,'cases':findings}


if __name__=='__main__':print(json.dumps(run(),indent=2))
