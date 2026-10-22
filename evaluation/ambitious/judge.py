"""Behavioral journey judge, never supplied to the workers or their repair loop."""
import copy,shutil,hashlib,importlib,io,json,os,random,sqlite3,subprocess,sys,tempfile,types,unittest,urllib.request,urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT)not in sys.path:sys.path.append(str(ROOT))
from evaluation.ambitious.cases import PUBLIC
from evaluation.ambitious.assertions import matches
GROUPS=['public','journey','atomicity','idempotency','isolation_or_revision','pagination_or_schedule','history_or_artifacts','recovery_or_returns','validation','backup','concurrency','transport','userdata']

def raises(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('Expected ValueError with no accepted mutation')

def seed(s,name):return importlib.import_module('evaluation.ambitious.check_'+name).seed(s)

def get(s,name):
    if name=='flowdesk':return s.call('ticket.list',{'workspace':'w','token':'a'})
    if name=='stockroom':return s.call('catalog',{})
    return s.call('workflow.get',{'id':'w'})

def parallel(repo,db,requests):
    barrier=db.parent/'barrier';barrier.unlink(missing_ok=True)
    code="""import json,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1]);from app import Service
until=time.monotonic()+5
while not Path(sys.argv[3]).exists():
 if time.monotonic()>until:raise RuntimeError('Barrier timeout')
 time.sleep(.005)
try:print(json.dumps({'ok':True,'result':Service(sys.argv[2]).call(*json.loads(sys.argv[4]))}))
except ValueError:print(json.dumps({'ok':False}))
"""
    ps=[subprocess.Popen([sys.executable,'-c',code,str(repo),str(db),str(barrier),json.dumps(r)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)for r in requests]
    barrier.write_text('go')
    results=[]
    for p in ps:
        out,err=p.communicate(timeout=12);assert p.returncode==0,err;results.append(json.loads(out))
    return results

def concurrency(s,name,repo,db):
    c=seed(s,name)
    if name=='flowdesk':
        c('ticket.create',id='t',title='Initial')
        requests=[('ticket.change',{'workspace':'w','token':'a','id':'t','expected_revision':1,'title':'Winner '+str(i)})for i in range(6)]
        values=parallel(repo,db,requests);assert sum(v['ok']for v in values)==1;assert c('ticket.get',id='t')['revision']==2
        for tid in('x','y'):c('ticket.create',id=tid,title='Issue')
        req=[('event.claim',{'workspace':'w','token':'a','worker':str(i),'now':0,'lease':10,'limit':1})for i in range(6)]
        rows=[r for x in parallel(repo,db,req)for r in x['result']];assert len(rows)==4 and len({r['sequence']for r in rows})==4
    elif name=='stockroom':
        c('stock.receive',sku='x',warehouse='a',quantity=5,key='r')
        for i in range(6):c('order.create',id=str(i),lines=[{'sku':'x','quantity':2}])
        values=parallel(repo,db,[('order.confirm',{'id':str(i)})for i in range(6)]);assert sum(v['ok']for v in values)==2;assert matches(c('stock.get',sku='x',warehouse='a'),{'on_hand':5,'reserved':4,'available':1})
    else:
        c('workflow.put',id='single',nodes=[{'id':'a','needs':[],'max_attempts':2}]);c('run.start',workflow='single',id='r',key='r')
        req=[('job.claim',{'worker':str(i),'now':0,'lease':10})for i in range(6)];first=[x['result']for x in parallel(repo,db,req)if x['result']is not None];assert len(first)==1
        req=[('job.claim',{'worker':str(i),'now':10,'lease':10})for i in range(6)];second=[x['result']for x in parallel(repo,db,req)if x['result']is not None];assert len(second)==1 and second[0]['attempt']==2
        raises(lambda:c('job.succeed',run='r',node='a',receipt=first[0]['receipt'],now=11,result=0));assert c('job.succeed',run='r',node='a',receipt=second[0]['receipt'],now=11,result=1)['status']=='succeeded'

def transport(repo,name,folder):
    db=folder/'transport.db';p=subprocess.Popen([sys.executable,str(repo/'transport.py'),'--db',str(db),'--serve','--port','0'],cwd=repo,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        import select
        assert select.select([p.stdout],[],[],7)[0],'HTTP server did not announce its port';port=json.loads(p.stdout.readline())['port'];base=f'http://127.0.0.1:{port}'
        assert json.loads(urllib.request.urlopen(base+'/health',timeout=4).read())['ok']
        def c(op,**kw):
            req=urllib.request.Request(base+'/api',data=json.dumps({'operation':op,'data':kw}).encode(),headers={'Content-Type':'application/json'})
            response=json.loads(urllib.request.urlopen(req,timeout=5).read());assert response['ok'];return response['result']
        if name=='flowdesk':
            c('bootstrap',workspace='w',token='a');c('ticket.create',workspace='w',token='a',id='t',title='HTTP ticket');c('ticket.change',workspace='w',token='a',id='t',expected_revision=1,status='pending');packet={'operation':'ticket.get','data':{'workspace':'w','token':'a','id':'t'}}
        elif name=='stockroom':
            c('product.put',sku='x',name='HTTP product');c('warehouse.add',id='a');c('stock.receive',sku='x',warehouse='a',quantity=6,key='r');c('order.create',id='o',lines=[{'sku':'x','quantity':4}]);c('order.confirm',id='o');c('order.ship',id='o',lines=[{'sku':'x','warehouse':'a','quantity':2}],key='s');packet={'operation':'stock.get','data':{'sku':'x','warehouse':'a'}}
        else:
            c('workflow.put',id='w',nodes=[{'id':'a','needs':[]}]);c('run.start',workflow='w',id='r',key='r');j=c('job.claim',worker='worker',now=0,lease=10);c('artifact.put',run='r',node='a',receipt=j['receipt'],now=1,name='doc',content='HTTP artifact');c('job.succeed',run='r',node='a',receipt=j['receipt'],now=2,result=7);packet={'operation':'artifact.get','data':{'run':'r','node':'a','name':'doc'}}
        try:c('not-a-real-operation')
        except urllib.error.HTTPError as e:assert e.code==400 and json.loads(e.read())['ok']is False
        else:raise AssertionError('HTTP invalid request accepted')
    finally:
        p.terminate()
        try:p.communicate(timeout=4)
        except subprocess.TimeoutExpired:p.kill();p.communicate()
    raw=json.dumps({'operation':'not-a-real-operation','data':{}})+'\n'+json.dumps(packet)+'\n'
    result=subprocess.run([sys.executable,str(repo/'transport.py'),'--db',str(db)],input=raw,text=True,capture_output=True,timeout=8,cwd=repo);assert result.returncode==0,result.stderr
    rows=[json.loads(x)for x in result.stdout.splitlines()];assert len(rows)==2 and rows[0]['ok']is False and rows[1]['ok']is True
    value=rows[1]['result']
    if name=='flowdesk':assert value['status']=='pending'and value['revision']==2
    elif name=='stockroom':assert matches(value,{'on_hand':4,'reserved':2,'available':2})
    else:assert value['content']=='HTTP artifact'

def backup(s,name,repo,folder):
    c=seed(s,name)
    if name=='flowdesk':c('ticket.create',id='t',title='Before backup');c('comment.add',ticket='t',id='n',text='Internal',internal=True)
    elif name=='stockroom':c('stock.receive',sku='x',warehouse='a',quantity=9,key='r');c('order.create',id='o',lines=[{'sku':'x','quantity':4}]);c('order.confirm',id='o')
    else:c('run.start',workflow='w',id='r',key='r');c('job.claim',worker='worker',now=0,lease=20)
    path=folder/'backup.json';s.backup(path);before=get(s,name);other=__import__('app').Service(folder/'other.db');other.restore(path);assert get(other,name)==before
    if name=='flowdesk':assert other.call('comment.list',{'workspace':'w','token':'a','ticket':'t'})[0]['internal']is True
    elif name=='stockroom':assert other.call('stock.get',{'sku':'x','warehouse':'a'})['reserved']==4
    else:assert other.call('run.get',{'id':'r'})['nodes'][0]['status']=='running'
    envelope=json.loads(path.read_text());bad=copy.deepcopy(envelope);bad['payload']['state']=[];body=json.dumps(bad['payload'],sort_keys=True,ensure_ascii=False,separators=(',',':'));bad['sha256']=hashlib.sha256(body.encode()).hexdigest();path.write_text(json.dumps(bad));raises(lambda:other.restore(path));assert get(other,name)==before
    bad=copy.deepcopy(envelope);bad['payload']['application']='another-application';body=json.dumps(bad['payload'],sort_keys=True,ensure_ascii=False,separators=(',',':'));bad['sha256']=hashlib.sha256(body.encode()).hexdigest();path.write_text(json.dumps(bad));raises(lambda:other.restore(path));assert get(other,name)==before
    raises(lambda:s.backup(folder/'state.sqlite'));link=folder/'db-hardlink';os.link(folder/'state.sqlite',link);raises(lambda:s.backup(link))

def check(name,repo,group,seed_value):
    sys.path.insert(0,str(repo));from app import Service
    if group=='public':
        module=types.ModuleType('public_acceptance');exec(compile(PUBLIC[name],'original_public_acceptance','exec'),module.__dict__);stream=io.StringIO();r=unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromModule(module));assert r.wasSuccessful(),stream.getvalue();return
    if group=='userdata':
        assert(repo/'USER_NOTES.txt').read_text()=='Original customer data: café 東京.\n'
        with sqlite3.connect(repo/'data/original.sqlite')as db:assert db.execute('SELECT id,value FROM notes').fetchall()==[(41,'Keep my unrelated table.')]
        with tempfile.TemporaryDirectory()as t:
            target=Path(t)/'copy.db';shutil.copy2(repo/'data/original.sqlite',target);s=Service(target)
            if name=='flowdesk':s.call('bootstrap',{'workspace':'userdata-'+str(seed_value),'token':'userdata-token-'+str(seed_value)})
            elif name=='stockroom':s.call('product.put',{'sku':'userdata-'+str(seed_value),'name':'Data preservation'})
            else:s.call('workflow.put',{'id':'userdata-'+str(seed_value),'nodes':[{'id':'node','needs':[]}]})
            with sqlite3.connect(target)as db:assert db.execute('SELECT id,value FROM notes').fetchall()==[(41,'Keep my unrelated table.')]
        return
    with tempfile.TemporaryDirectory()as t:
        folder=Path(t);db=folder/'state.sqlite';s=Service(db);rng=random.Random(seed_value)
        if group=='transport':transport(repo,name,folder)
        elif group=='concurrency':concurrency(s,name,repo,db)
        elif group=='backup':backup(s,name,repo,folder)
        else:importlib.import_module('evaluation.ambitious.check_'+name).check(s,group,rng,raises,repo)


def evaluate(name,repo,seed=90173,groups=None):
    from goalpilot.process import run_process
    results=[]
    for group in groups or GROUPS:
        result=run_process([sys.executable,str(Path(__file__).resolve()),name,str(Path(repo).resolve()),group,str(seed)],ROOT,30)
        try:value=json.loads(result.output.splitlines()[-1])
        except (ValueError,IndexError):value={'passed':False,'error':result.output[-4000:]or'Judge timed out'}
        results.append({'id':group,**value,'judge_seconds':result.duration_seconds,'judge_timed_out':result.timed_out})
    return results


if __name__=='__main__':
    try:check(sys.argv[1],Path(sys.argv[2]),sys.argv[3],int(sys.argv[4]));print(json.dumps({'passed':True}))
    except Exception as exc:
        import traceback
        print(json.dumps({'passed':False,'error':f'{type(exc).__name__}: {exc}','traceback':traceback.format_exc()[-5000:]}))
