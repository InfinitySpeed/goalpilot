"""Additional public worker journeys; baseline component judge remains unchanged."""
import copy,json,sys,tempfile,urllib.request,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT)not in sys.path:sys.path.append(str(ROOT))
from evaluation.ambitious.judge import raises,parallel
GROUPS=['worker_journey','worker_retry_cancel','worker_revisions','worker_validation','worker_concurrency','worker_transport_restore']


def check(repo,group):
    sys.path.insert(0,str(repo));from app import Service
    with tempfile.TemporaryDirectory()as t:
        folder=Path(t);db=folder/'db';s=Service(db)
        def c(op,**kw):return s.call(op,kw)
        def put(nodes):return c('workflow.put',id='w',nodes=nodes)
        def start(rid='r'):return c('run.start',workflow='w',id=rid,key=rid)
        def node(nid,op='emit',needs=[],**task):return{'id':nid,'needs':needs,'task':{'op':op,**task}}
        if group=='worker_journey':
            put([node('a',value=7),node('b',value=9),node('sum','sum',['a','b']),node('artifact','artifact',['sum'],name='résultat',content='café 東京'),node('all','collect',['sum','artifact'])]);start();out=c('worker.tick',worker='w',now=0,limit=100);assert len(out)==5 and all(x['status']=='succeeded'for x in out)
            r=c('run.get',id='r');assert r['status']=='succeeded';values={n['id']:n['result']for n in r['nodes']};assert values['sum']==16 and values['all']['sum']==16;assert c('artifact.get',run='r',node='artifact',name='résultat')['content']=='café 東京';assert c('worker.tick',worker='x',now=50)==[]
        elif group=='worker_retry_cancel':
            bad=node('bad','fail',message='expected');bad.update(max_attempts=3,retry_delay=5);put([bad,node('child','sum',['bad']),node('ok',value=42)]);start();out=c('worker.tick',worker='w',now=0,limit=10);assert len(out)==2 and {x['status']for x in out}=={'retry','succeeded'};assert c('worker.tick',worker='w',now=4)==[];assert c('worker.tick',worker='w',now=5)[0]['status']=='retry';assert c('worker.tick',worker='w',now=10)[0]['status']=='failed';assert c('run.get',id='r')['status']=='failed'
            bad['retry_delay']=0;put([bad]);start('s');assert len(c('worker.tick',worker='w',now=20,limit=2))==2;c('run.cancel',id='s');assert c('worker.tick',worker='w',now=20,limit=10)==[]
        elif group=='worker_revisions':
            put([node('a',value={'original':[1,2]})]);start();put([node('a',value='replacement')]);start('s');out=c('worker.tick',worker='w',now=0);assert [x['result']for x in out]==[{'original':[1,2]},'replacement'];assert c('run.get',id='r')['nodes'][0]['task']['value']=={'original':[1,2]}
            put([node('a',value='A'),node('b',value='B'),node('z','join',['b','a'],separator=':')]);start('t');c('worker.tick',worker='w',now=1);assert next(n for n in c('run.get',id='t')['nodes']if n['id']=='z')['result']=='A:B'
        elif group=='worker_validation':
            old=put([node('a',value=1)])
            for task in(None,{'op':'unknown'},{'op':'artifact','name':'x','content':4},{'op':'join','separator':True}):raises(lambda task=task:put([{'id':'a','needs':[],'task':task}]))
            assert c('workflow.get',id='w')==old;start()
            for kw in({'now':True},{'now':0,'limit':True},{'now':0,'lease':0}):raises(lambda kw=kw:c('worker.tick',worker='w',**kw))
            assert c('run.get',id='r')['nodes'][0]['attempt']==0
            put([node('a',value=True),node('b','sum',['a'])]);start('s');c('worker.tick',worker='w',now=0,limit=10);assert c('run.get',id='s')['status']=='failed'
        elif group=='worker_concurrency':
            put([node(str(i),value=i)for i in range(6)]);start();req=[('worker.tick',{'worker':str(i),'now':0,'limit':1})for i in range(9)];rows=[r for p in parallel(repo,db,req)for r in p['result']];assert len(rows)==6 and len({r['node']for r in rows})==6 and c('run.get',id='r')['status']=='succeeded'
            put([node('a',value=1)]);start('s');j=c('job.claim',worker='manual',now=10,lease=10);assert c('worker.tick',worker='auto',now=11)==[];c('job.succeed',run='s',node='a',receipt=j['receipt'],now=12,result=1)
        elif group=='worker_transport_restore':
            import select
            p=subprocess.Popen([sys.executable,str(repo/'transport.py'),'--db',str(db),'--serve','--port','0'],cwd=repo,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                assert select.select([p.stdout],[],[],5)[0];port=json.loads(p.stdout.readline())['port']
                def http(op,**kw):
                    req=urllib.request.Request(f'http://127.0.0.1:{port}/api',data=json.dumps({'operation':op,'data':kw}).encode());r=json.loads(urllib.request.urlopen(req,timeout=5).read());assert r['ok'];return r['result']
                http('workflow.put',id='w',nodes=[node('a',value=7),node('b','sum',['a'])]);http('run.start',workflow='w',id='r',key='r');assert len(http('worker.tick',worker='w',now=0,limit=1))==1
            finally:
                p.terminate()
                try:p.communicate(timeout=3)
                except subprocess.TimeoutExpired:p.kill();p.communicate()
            backup=folder/'saved.json';s.backup(backup);other=Service(folder/'restore');other.restore(backup);assert other.call('worker.tick',{'worker':'w','now':0})[0]['result']==7
            raw=json.dumps({'operation':'worker.tick','data':{'worker':'cli','now':0}})+'\n';out=subprocess.check_output([sys.executable,str(repo/'transport.py'),'--db',str(db)],input=raw,text=True,timeout=7);assert json.loads(out)['result'][0]['result']==7


def evaluate(repo):
    from goalpilot.process import run_process
    result=[]
    for group in GROUPS:
        r=run_process([sys.executable,str(Path(__file__).resolve()),str(repo),group],ROOT,30)
        try:value=json.loads(r.output.splitlines()[-1])
        except(ValueError,IndexError):value={'passed':False,'error':r.output[-3000:]}
        result.append({'id':group,**value,'judge_seconds':r.duration_seconds})
    return result


if __name__=='__main__':
    try:check(Path(sys.argv[1]),sys.argv[2]);print(json.dumps({'passed':True}))
    except Exception as e:
        import traceback
        print(json.dumps({'passed':False,'error':f'{type(e).__name__}: {e}','traceback':traceback.format_exc()[-4000:]}))
