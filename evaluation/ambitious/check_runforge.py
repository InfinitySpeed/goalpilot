from evaluation.ambitious.assertions import matches
import hashlib

def seed(s):
    def c(op,**kw):return s.call(op,kw)
    c('workflow.put',id='w',nodes=[{'id':'a','needs':[],'max_attempts':2,'retry_delay':3},{'id':'b','needs':['a']}])
    return c

def check(s,group,rng,raises,repo):
    c=seed(s)
    def start(rid='r',key='k'):return c('run.start',workflow='w',id=rid,key=key)
    def claim(now=0,lease=10):return c('job.claim',worker='worker',now=now,lease=lease)
    def finish(job,now=1):return c('job.succeed',run=job['run'],node=job['node'],receipt=job['receipt'],now=now,result={'value':42})
    if group=='journey':
        start();a=claim();blob=c('artifact.put',run='r',node='a',receipt=a['receipt'],now=1,name='report',content='café 東京');assert blob['size']==len('café 東京'.encode());finish(a)
        b=claim(2);assert b['node']=='b';assert finish(b,3)['status']=='succeeded';assert c('artifact.get',run='r',node='a',name='report')['content']=='café 東京'
        c('workflow.put',id='w',nodes=[{'id':'next','needs':[]}]);assert c('run.get',id='r')['revision']==1
    elif group=='atomicity':
        before=c('workflow.get',id='w');raises(lambda:c('workflow.put',id='w',nodes=[{'id':'a','needs':['b']},{'id':'b','needs':['a']}]));assert c('workflow.get',id='w')==before
        c('schedule.put',id='z',workflow='w',start=0,interval=1,limit=3);start('@z:1','conflict');raises(lambda:c('schedule.tick',now=5,max_runs=3));assert c('schedule.get',id='z')['emitted']==0;raises(lambda:c('run.get',id='@z:0'))
        c('run.cancel',id='@z:1');c('run.delete',id='@z:1');assert [r['id']for r in c('schedule.tick',now=5,max_runs=3)]==['@z:0','@z:1','@z:2']
    elif group=='idempotency':
        first=start();finish(claim());assert start()==first;raises(lambda:start('other','k'));assert len(c('run.list')['items'])==1
        finish(claim(2),3);c('run.delete',id='r');assert start()['status']=='active';assert c('run.get',id='r')['nodes'][0]['attempt']==0
    elif group=='isolation_or_revision':
        start();c('workflow.put',id='w',nodes=[{'id':'changed','needs':[]}]);c('workflow.put',id='w',nodes=[{'id':'changed','needs':[]}]);assert c('workflow.get',id='w')['revision']==3
        assert [n['id']for n in c('run.get',id='r')['nodes']]==['a','b'];assert start('s','s')['revision']==3
        a=claim();finish(a);b=claim(2);assert b['run']=='r'and b['node']=='b';finish(b,3);assert claim(4)['node']=='changed'
    elif group=='pagination_or_schedule':
        c('schedule.put',id='a',workflow='w',start=0,interval=10,limit=2);c('schedule.put',id='z',workflow='w',start=0,interval=5,limit=3)
        assert [r['id']for r in c('schedule.tick',now=20,max_runs=3)]==['@a:0','@z:0','@z:1']
        c('workflow.put',id='w',nodes=[{'id':'c','needs':[]}]);rows=c('schedule.tick',now=20,max_runs=100);assert [r['id']for r in rows]==['@a:1','@z:2']and all(r['revision']==2 for r in rows)
        assert c('schedule.tick',now=100,max_runs=5)==[];x=c('run.list',limit=2);assert [r['id']for r in x['items']]==['@a:0','@a:1']and x['next']=='@a:1'
        c('run.cancel',id='@a:1');c('run.delete',id='@a:1');assert [r['id']for r in c('run.list',after='@a:1',limit=100)['items']]==['@z:0','@z:1','@z:2']
    elif group=='history_or_artifacts':
        c('workflow.put',id='single',nodes=[{'id':'a','needs':[]}]);content='café 東京';digest=hashlib.sha256(content.encode()).hexdigest()
        for rid in('x','y'):
            c('run.start',workflow='single',id=rid,key=rid);j=claim();v=c('artifact.put',run=rid,node='a',receipt=j['receipt'],now=1,name='doc',content=content);assert matches(v,{'digest':digest,'size':len(content.encode())});finish(j)
        c('run.delete',id='x');assert matches(c('artifact.gc'),{'removed':0,'remaining':1});assert c('artifact.get',run='y',node='a',name='doc')['content']==content
        c('run.delete',id='y');assert matches(c('artifact.gc'),{'removed':1,'remaining':0})
    elif group=='recovery_or_returns':
        start();a=claim(10,5);raises(lambda:c('job.succeed',run='r',node='a',receipt=a['receipt'],now=15,result=1));assert claim(15)is None
        b=claim(18);assert b['attempt']==2 and b['receipt']!=a['receipt'];raises(lambda:c('artifact.put',run='r',node='a',receipt=a['receipt'],now=19,name='bad',content='orphan'))
        assert matches(c('artifact.gc'),{'removed':0,'remaining':0});x=c('job.fail',run='r',node='a',receipt=b['receipt'],now=19,error='broken');assert x['status']=='failed'and [n['status']for n in x['nodes']]==['failed','skipped'];assert claim(100)is None
        start('s','s');fresh=claim(101);c('run.cancel',id='s');raises(lambda:finish(fresh,102));assert c('run.get',id='s')['status']=='cancelled'
    elif group=='validation':
        for nodes in ([{'id':'a','needs':['missing']}],[{'id':'a','needs':[],'max_attempts':True}],[{'id':'a','needs':[]},{'id':'a','needs':[]}],[{'id':'a','needs':['a']}],[]):raises(lambda nodes=nodes:c('workflow.put',id='invalid',nodes=nodes))
        raises(lambda:c('job.claim',worker='x',now=True,lease=2));raises(lambda:c('run.list',limit=True))
        nodes=[{'id':str(i),'needs':[str(j)for j in range(i)if rng.random()<.35]}for i in range(7)];c('workflow.put',id='random',nodes=nodes);c('run.start',workflow='random',id='property',key='property');done=set()
        for i in range(7):
            j=claim(i*3);assert j and set(nodes[int(j['node'])]['needs'])<=done;finish(j,i*3+1);done.add(j['node'])
        assert c('run.get',id='property')['status']=='succeeded'and len(done)==7
    return c
