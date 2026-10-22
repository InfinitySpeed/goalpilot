"""Attainability, public-gate consistency, and sensitivity to each semantic fault."""
import json,shutil,subprocess,sys,tempfile
from pathlib import Path
from .cases import materialize,reference,faults
from .judge import evaluate


def install(repo,name,text):
    (repo/name/'core.py').write_text(text)
    for path in repo.rglob('__pycache__'):shutil.rmtree(path)


def run():
    findings=[]
    for name in ('daybook','tablekit','resolver'):
        with tempfile.TemporaryDirectory()as t:
            repo=Path(t)/'repo';materialize(name,repo)
            initial=evaluate(name,repo)
            assert any(not x['passed']for x in initial)
            assert not next(x for x in initial if x['id']=='public')['passed']
            install(repo,name,reference(name));good=evaluate(name,repo)
            assert all(x['passed']for x in good),(name,good)
            mutants=[]
            for index,(before,after)in enumerate(faults(name)):
                text=reference(name);assert before in text;install(repo,name,text.replace(before,after,1))
                results=evaluate(name,repo);rejected=[x['id']for x in results if not x['passed']]
                assert rejected,(name,index,'undetected semantic fault')
                mutants.append({'fault':index+1,'rejected_by':rejected})
            findings.append({'case':name,'initial_failed_groups':[x['id']for x in initial if not x['passed']],
                'reference_passed_groups':len(good),'single_semantic_faults':mutants})
    return {'model_calls':0,'cases':findings}


if __name__=='__main__':print(json.dumps(run(),indent=2))
