"""Hidden independent behavioral groups; no feedback is supplied to model repair."""
import copy,datetime,hashlib,importlib,importlib.util,io,itertools,json,random,sqlite3,subprocess,sys,tempfile,types,unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT)not in sys.path:sys.path.append(str(ROOT))
from evaluation.triple.cases import PUBLIC
GROUPS=['public','interaction','edge','persistence_or_graph','validation_or_order','userdata']


def oracle(name):
    spec=importlib.util.spec_from_file_location('reference_'+name,Path(__file__).with_name('reference_'+name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def raises(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('Expected ValueError')

def simple_expected(catalog,requests,locked):
    names=sorted(catalog);solutions=[]
    def meets(v,c):return c=='*'or v.startswith(c[0]+'.')
    for choices in itertools.product(*[[None]+[r['version']for r in catalog[n]]for n in names]):
        chosen={n:v for n,v in zip(names,choices)if v};needed=set(requests);todo=list(needed);valid=True
        while todo:
            n=todo.pop()
            if n not in chosen:valid=False;break
            row=next(r for r in catalog[n]if r['version']==chosen[n])
            for dep in row['dependencies']:
                if dep not in needed:needed.add(dep);todo.append(dep)
        if not valid or set(chosen)!=needed:continue
        if any(not meets(chosen[n],c)for n,c in requests.items()):continue
        if any(not meets(chosen[d],c)for n in needed for r in catalog[n]if r['version']==chosen[n]for d,c in r['dependencies'].items()):continue
        constraints={n:[c]for n,c in requests.items()};seen=set();rank=[]
        while set(constraints)-seen:
            n=min(set(constraints)-seen)
            candidates=[r for r in catalog[n]if all(meets(r['version'],c)for c in constraints[n])]
            candidates.sort(key=lambda r:(r['version']!=locked.get(n),-int(r['version'][0])))
            rank.append(next(i for i,r in enumerate(candidates)if r['version']==chosen[n]));seen.add(n)
            row=next(r for r in catalog[n]if r['version']==chosen[n])
            for dep,c in row['dependencies'].items():constraints.setdefault(dep,[]).append(c)
        solutions.append((tuple(rank),dict(sorted(chosen.items()))))
    return min(solutions,key=lambda x:x[0])[1]if solutions else None


def check(name,repo,group,seed):
    sys.path.insert(0,str(repo));api=importlib.import_module(name);rng=random.Random(seed)
    if group=='public':
        m=types.ModuleType('public_acceptance');exec(compile(PUBLIC[name],'original_public_tests','exec'),m.__dict__)
        stream=io.StringIO();res=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromModule(m))
        assert res.wasSuccessful(),stream.getvalue()[-6000:];return
    if group=='userdata':
        assert (repo/'USER_NOTES.txt').read_text()=='Mes données originales: café 東京.\n'
        if name=='tablekit':assert (repo/'data/source.csv').read_text()=='name,value\n"café, 東京",0.10\n'
        elif name=='resolver':assert (repo/'data/lock.json').read_text()=='{"local":"1.0.0"}\n'
        else:
            with sqlite3.connect(repo/'data/legacy.sqlite')as db:
                rows=db.execute('select id,spec from schedules').fetchall();assert len(rows)==1 and rows[0][0]=='old'
                assert json.loads(rows[0][1])=={'start_date':'2026-01-01','at':'09:00','zone':'UTC','count':2}
                assert db.execute('select value from notes').fetchone()[0]=='keep'
        return
    if name=='daybook':
        if group=='interaction':
            base={'start_date':'2026-03-08','until':'2026-03-08','at':'02:30','zone':'America/New_York'}
            assert api.occurrences(base,'2026-03-08T00:00:00Z','2026-03-09T00:00:00Z')==[]
            assert api.occurrences({**base,'gap':'next_valid'},'2026-03-08T00:00:00Z','2026-03-09T00:00:00Z')==['2026-03-08T07:00:00Z']
            half={'start_date':'2026-10-04','until':'2026-10-04','at':'02:15','zone':'Australia/Lord_Howe','gap':'next_valid'}
            assert api.occurrences(half,'2026-10-03T00:00:00Z','2026-10-05T00:00:00Z')==['2026-10-03T15:30:00Z']
        elif group=='edge':
            ref=oracle(name)
            for i in range(20):
                spec={'start_date':'2026-03-01','at':rng.choice(['01:30','02:30','09:00']),'zone':rng.choice(['UTC','America/New_York','Europe/Paris']),
                      'weekdays':sorted(rng.sample(range(7),rng.randrange(1,8))),'count':rng.randrange(1,12),'exclude':['2026-03-02'],'gap':rng.choice(['skip','next_valid'])}
                original=copy.deepcopy(spec);lo='2026-03-01T00:00:00Z';mid='2026-03-10T00:00:00Z';hi='2026-04-01T00:00:00Z'
                full=api.occurrences(spec,lo,hi);assert full==ref.occurrences(spec,lo,hi)
                assert full==api.occurrences(spec,lo,mid)+api.occurrences(spec,mid,hi)
                assert spec==original
        elif group=='persistence_or_graph':
            with tempfile.TemporaryDirectory()as t:
                db=Path(t)/'nested/a.db';s={'start_date':'2026-01-01','at':'09:00','zone':'UTC','count':2}
                store=api.ScheduleStore(db);assert store.put('x',s)['revision']==1
                assert store.update('x',s,1)['revision']==2
                raises(lambda:store.update('x',s,1));assert api.ScheduleStore(db).get('x')['revision']==2
                code="""import sys,json
sys.path.insert(0,sys.argv[1]);from daybook import ScheduleStore
s={'start_date':'2026-01-01','at':'10:00','zone':'UTC','count':2}
try:ScheduleStore(sys.argv[2]).update('x',s,2);print('ok')
except ValueError:print('conflict')
"""
                def work(_):return subprocess.check_output([sys.executable,'-c',code,str(repo),str(db)],text=True,timeout=10).strip()
                with ThreadPoolExecutor(5)as pool:results=list(pool.map(work,range(5)))
                assert results.count('ok')==1 and results.count('conflict')==4,results
                assert api.ScheduleStore(db).get('x')['revision']==3
                before=api.ScheduleStore(db).get('x');raises(lambda:store.update('x',{**s,'count':True},3));assert store.get('x')==before
                import shutil
                legacy=Path(t)/'legacy.db';shutil.copyfile(repo/'data/legacy.sqlite',legacy)
                migrated=api.ScheduleStore(legacy);assert migrated.get('old')['revision']==1
                assert migrated.due('2026-01-01T00:00:00Z','2026-01-04T00:00:00Z')==[{'id':'old','at':'2026-01-01T09:00:00Z'},{'id':'old','at':'2026-01-02T09:00:00Z'}]
        else:
            s={'start_date':'2026-01-01','at':'09:00','zone':'UTC'}
            for change in ({'count':True},{'weekdays':[0,0]},{'at':'24:00'},{'start_date':'2026-02-30'},{'zone':'No/SuchZone'},{'exclude':['bad']},{'extra':1}):
                raises(lambda c=change:api.occurrences({**s,**c},'2026-01-01T00:00:00Z','2026-01-04T00:00:00Z'))
            for lo,hi in [('2026-01-01','2026-01-03T00:00:00Z'),('2026-01-02T00:00:00Z','2026-01-01T00:00:00Z')]:raises(lambda:api.occurrences(s,lo,hi))
    elif name=='tablekit':
        if group=='interaction':
            values=[None,'','\\N','\\\\N','\\abc','\\\\abc','café, 東京','quote"\nline']
            t={'columns':['value'],'rows':[[x]for x in values]};before=copy.deepcopy(t)
            assert api.read_csv(api.write_csv(t))==t;assert t==before
            assert api.write_csv(t).endswith('\n')
        elif group=='edge':
            for i in range(12):
                huge=str(10**(40+i)+rng.randrange(1,100));decimal='0.'+'0'*i+'17'
                t={'a':{'columns':['k','n'],'rows':[['x',huge],['x',decimal],['x','-'+huge],['y',None]]}}
                p={'source':'a','group_by':['k'],'aggregates':[{'as':'total','op':'sum','column':'n'},{'as':'n','op':'count','column':'*'}]}
                original=copy.deepcopy(t);assert api.execute(p,t)=={'columns':['k','total','n'],'rows':[['x',decimal,3],['y',None,1]]}
                assert t==original
            assert api.execute({'source':'a','aggregates':[{'as':'n','op':'count','column':'*'},{'as':'s','op':'sum','column':'x'}]}, {'a':{'columns':['x'],'rows':[]}})=={'columns':['n','s'],'rows':[[0,None]]}
        elif group=='persistence_or_graph':
            ref=oracle(name)
            for i in range(20):
                cells=[None,'a','b','c'];left=[[rng.choice(cells),rng.choice(cells)]for _ in range(5)];right=[[rng.choice(cells),rng.choice(cells),str(n)]for n in range(7)]
                t={'a':{'columns':['x','y'],'rows':left},'b':{'columns':['x','y','n'],'rows':right}}
                p={'source':'a','joins':[{'table':'b','left_on':['x','y'],'right_on':['x','y'],'kind':rng.choice(['inner','left']),'prefix':'r'}]}
                before=copy.deepcopy((p,t));assert api.execute(p,t)==ref.execute(p,t);assert(p,t)==before
            t={'a':{'columns':['x'],'rows':[['a'],['b'],[None]]}}
            assert api.execute({'source':'a','where':[{'column':'x','op':'not_in','value':['z',None]}]},t)['rows']==[]
        else:
            t={'a':{'columns':['key','n'],'rows':[['a','2'],['b',None],['c','10'],['d','2']]}}
            p={'source':'a','order_by':[{'column':'n','descending':True,'nulls':'last','numeric':True}],'select':['key'],'limit':3}
            assert api.execute(p,t)=={'columns':['key'],'rows':[['c'],['a'],['d']]}
            for plan in ({'source':'a','limit':True},{'source':'a','where':[{'column':'missing','op':'eq','value':'x'}]},{'source':'a','order_by':[{'column':'key','numeric':True}]}):
                before=copy.deepcopy(t);raises(lambda:api.execute(plan,t));assert t==before
            empty={'a':{'columns':['x'],'rows':[]}}
            raises(lambda:api.execute({'source':'a','where':[{'column':'x','op':'wrong','value':'a'}]},empty))
            for text in ('a,a\n1,2\n','a,b\n1\n','a\n"unterminated') :raises(lambda:api.read_csv(text))
    else:
        if group=='interaction':
            seq=['1.0.0-alpha','1.0.0-alpha.1','1.0.0-alpha.beta','1.0.0-beta','1.0.0-beta.2','1.0.0-beta.11','1.0.0-rc.1','1.0.0']
            for a,b in zip(seq,seq[1:]):assert api.compare_versions(a,b)==-1
            assert api.compare_versions('1.0.0+a','1.0.0+b')==0
            for v in ('01.0.0','1.0','1.0.0-01','v1.0.0','1.0.0-','1.0.0+a..b',True):raises(lambda:api.compare_versions(v,'1.0.0'))
        elif group=='edge':
            assert not api.satisfies('1.0.0-beta','<1.0.0-alpha || *')
            assert api.satisfies('1.0.0-beta','<1.0.0-alpha || *',allow_prerelease=True)
            assert api.satisfies('1.0.0-beta','>=1.0.0-alpha <1.0.0')
            assert not api.satisfies('2.0.0-beta','>=1.0.0-alpha <3.0.0')
            for v,c,want in [('1.2.9','~1.2.3',True),('1.3.0','~1.2.3',False),('0.0.4','^0.0.3',False),('2.9.0','2.*',True),('3.0.0','2.*',False)]:assert api.satisfies(v,c)==want
            raises(lambda:api.satisfies('1.0.0','* || junk'));raises(lambda:api.satisfies('1.0.0','01.*'));raises(lambda:api.satisfies('1.0.0','*',allow_prerelease=1))
        elif group=='persistence_or_graph':
            for i in range(24):
                catalog={n:[{'version':f'{v}.0.0','dependencies':{d:rng.choice(['*','1.*','2.*'])for d in ['a','b','c']if d!=n and rng.random()<.3}}for v in (1,2)]for n in ['a','b','c']}
                req={'a':rng.choice(['*','1.*','2.*'])};locked={'b':rng.choice(['1.0.0','2.0.0'])};before=copy.deepcopy((catalog,req,locked));expected=simple_expected(catalog,req,locked)
                try:actual=api.resolve(catalog,req,locked)
                except api.ResolutionError:actual=None
                assert actual==expected,(catalog,req,locked,actual,expected)
                assert(catalog,req,locked)==before
        else:
            c={'a':[{'version':'1.0.0','dependencies':{}},{'version':'2.0.0','dependencies':{}},{'version':'3.0.0','dependencies':{},'yanked':True}]}
            assert api.resolve(c,{'a':'>=2.0.0'},{'a':'1.0.0'})=={'a':'2.0.0'}
            assert api.resolve(c,{'a':'*'},{'a':'99.0.0'})=={'a':'2.0.0'}
            assert api.resolve(c,{'a':'*'},{'a':'3.0.0'})=={'a':'2.0.0'}
            tied={'a':[{'version':'1.0.0+b','dependencies':{}},{'version':'1.0.0+a','dependencies':{}}]}
            assert api.resolve(tied,{'a':'*'})=={'a':'1.0.0+a'}
            raises(lambda:api.resolve({**c,'unused':[{'version':'bad','dependencies':{}}]},{}))
            raises(lambda:api.resolve(c,{'a':'*'},allow_prerelease=1))


def evaluate(name,repo,seed=91027,timeout=30):
    from goalpilot.process import run_process
    results=[]
    for group in GROUPS:
        result=run_process([sys.executable,str(Path(__file__).resolve()),name,str(Path(repo).resolve()),group,str(seed)],ROOT,timeout)
        try:value=json.loads(result.output.splitlines()[-1])
        except (ValueError,IndexError):value={'passed':False,'error':result.output[-4000:]or 'judge timed out/failed'}
        results.append({'id':group,**value,'judge_seconds':result.duration_seconds,'judge_timed_out':result.timed_out})
    return results


if __name__=='__main__':
    try:check(sys.argv[1],Path(sys.argv[2]),sys.argv[3],int(sys.argv[4]));print(json.dumps({'passed':True}))
    except Exception as exc:
        import traceback
        print(json.dumps({'passed':False,'error':f'{type(exc).__name__}: {exc}','traceback':traceback.format_exc()[-5000:]}))
