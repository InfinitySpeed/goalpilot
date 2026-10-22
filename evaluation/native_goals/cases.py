from pathlib import Path
from evaluation.ambitious.cases import materialize as base
from evaluation.ambitious.specs import RUN,GOALS as OLD_GOALS
from evaluation.ambitious.judge import evaluate as base_judge
from .worker import reference,SPEC
from .worker_judge import evaluate as worker_judge
GOALS={'runforge':OLD_GOALS['runforge'],'automation':'Finish this whole local automation platform so I can define a graph of real tasks, execute it with workers, recover expired work, fetch outputs and artifacts, and resume after restart. Deliver all original workflows through the API, CLI and HTTP autonomously, preserving existing data.'}
SPECS={'runforge':RUN,'automation':SPEC}


def materialize(repo,name,reference_code=False):
    repo=base(repo,'runforge',reference_code)
    if name=='automation':
        (repo/'README.md').write_text(SPEC)
        if reference_code:(repo/'engine.py').write_text(reference())
    return repo


def judge(name,repo):
    rows=[]
    for seed in(90173,470117):rows.extend({**r,'seed':seed}for r in base_judge('runforge',repo,seed))
    if name=='automation':rows.extend({**r,'seed':None}for r in worker_judge(repo))
    return rows
