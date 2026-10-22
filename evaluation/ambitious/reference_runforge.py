import copy,hashlib
APPLICATION='runforge'
TERMINAL={'succeeded','failed','skipped','cancelled'}
def initial():return {'workflows':{},'runs':{},'keys':{},'blobs':{},'schedules':{},'receipts':0}
def ident(x):
    if not isinstance(x,str)or not x:raise ValueError('Expected nonempty ID/text')
    return x
def number(x,lo=0,hi=None):
    if type(x)is not int or x<lo or hi is not None and x>hi:raise ValueError('Invalid integer')
    return x
def graph(values):
    if not isinstance(values,list)or not values:raise ValueError('Nonempty graph required')
    nodes={}
    for row in values:
        if not isinstance(row,dict):raise ValueError('Invalid node')
        nid=ident(row.get('id'));needs=row.get('needs')
        if nid in nodes or not isinstance(needs,list)or any(not isinstance(v,str)or not v for v in needs)or len(set(needs))!=len(needs):raise ValueError('Invalid node/dependencies')
        nodes[nid]={'id':nid,'needs':sorted(needs),'max_attempts':number(row.get('max_attempts',1),1),'retry_delay':number(row.get('retry_delay',0))}
    visiting=set();done=set()
    def visit(nid):
        if nid not in nodes or nid in visiting:raise ValueError('Missing dependency or cycle')
        if nid in done:return
        visiting.add(nid)
        for dep in nodes[nid]['needs']:visit(dep)
        visiting.remove(nid);done.add(nid)
    for nid in nodes:visit(nid)
    return[nodes[nid]for nid in sorted(nodes)]
def snapshot(r):
    nodes=[]
    for nid,n in sorted(r['nodes'].items()):
        item={k:n[k]for k in('id','status','attempt','not_before')}
        for field in('result','error'):
            if field in n:item[field]=copy.deepcopy(n[field])
        nodes.append(item)
    return{'id':r['id'],'workflow':r['workflow'],'revision':r['revision'],'status':r['status'],'nodes':nodes}
def refresh(r):
    if r['status']=='cancelled':return
    for _ in r['nodes']:
        for n in r['nodes'].values():
            statuses=[r['nodes'][dep]['status']for dep in n['needs']]
            if n['status']in('blocked','ready')and any(v in('failed','skipped','cancelled')for v in statuses):n['status']='skipped'
            elif n['status']=='blocked'and all(v=='succeeded'for v in statuses):n['status']='ready'
    values=[n['status']for n in r['nodes'].values()]
    r['status']='succeeded'if all(v=='succeeded'for v in values)else'failed'if all(v in TERMINAL for v in values)else'active'
def new_run(s,wid,rid):
    if wid not in s['workflows']or rid in s['runs']:raise ValueError('Missing workflow or duplicate run')
    w=s['workflows'][wid];nodes={}
    for item in w['nodes']:
        n=copy.deepcopy(item);n.update(status='blocked'if n['needs']else'ready',attempt=0,not_before=0,attachments={});nodes[n['id']]=n
    r={'id':rid,'workflow':wid,'revision':w['revision'],'status':'active','nodes':nodes};s['runs'][rid]=r;return r

def validate_state(s):
    try:
        assert isinstance(s,dict)
        for key in('workflows','runs','keys','blobs','schedules'):assert isinstance(s[key],dict)
        number(s['receipts'])
        for wid,w in s['workflows'].items():assert wid==w['id'];ident(wid);number(w['revision'],1);graph(w['nodes'])
        for rid,r in s['runs'].items():
            assert rid==r['id']and r['workflow']in s['workflows'];number(r['revision'],1);assert r['status']in('active','succeeded','failed','cancelled');graph(list(r['nodes'].values()))
            for nid,n in r['nodes'].items():
                assert nid==n['id']and n['status']in('blocked','ready','running',*TERMINAL);number(n['attempt'],0,n['max_attempts']);number(n['not_before']);assert isinstance(n['attachments'],dict)
                if n['status']=='running':ident(n['receipt']);number(n['expires']);assert n['attempt']>=1
                for name,digest in n['attachments'].items():ident(name);assert digest in s['blobs']
        for digest,content in s['blobs'].items():assert isinstance(content,str)and hashlib.sha256(content.encode()).hexdigest()==digest
        for sid,sch in s['schedules'].items():
            ident(sid);assert sid==sch['id']and sch['workflow']in s['workflows'];number(sch['start']);number(sch['interval'],1);number(sch['limit'],1);number(sch['emitted'],0,sch['limit'])
        for key,item in s['keys'].items():ident(key);assert item['request']['id']in s['runs']and isinstance(item['result'],dict)
    except (AssertionError,KeyError,TypeError,AttributeError,ValueError)as exc:raise ValueError('Invalid domain backup')from exc

def handle(s,op,d):
    def run(rid):
        ident(rid)
        if rid not in s['runs']:raise ValueError('Missing run')
        return s['runs'][rid]
    def current():
        r=run(d.get('run'));nid=ident(d.get('node'));receipt=ident(d.get('receipt'));now=number(d.get('now'))
        n=r['nodes'].get(nid)
        if not n or n['status']!='running'or n.get('receipt')!=receipt or now>=n['expires']or r['status']=='cancelled':raise ValueError('Invalid or expired claim')
        return r,n,now
    if op=='workflow.put':
        wid=ident(d.get('id'));nodes=graph(d.get('nodes'));old=s['workflows'].get(wid);w={'id':wid,'revision':old['revision']+1 if old else 1,'nodes':nodes};s['workflows'][wid]=w;return w
    if op=='workflow.get':
        wid=ident(d.get('id'))
        if wid not in s['workflows']:raise ValueError('Missing workflow')
        return s['workflows'][wid]
    if op=='run.start':
        wid=ident(d.get('workflow'));rid=ident(d.get('id'));key=ident(d.get('key'));request={'workflow':wid,'id':rid}
        if key in s['keys']:
            if s['keys'][key]['request']!=request:raise ValueError('Idempotency conflict')
            return s['keys'][key]['result']
        result=snapshot(new_run(s,wid,rid));s['keys'][key]={'request':request,'result':copy.deepcopy(result)};return result
    if op=='run.get':return snapshot(run(d.get('id')))
    if op=='job.claim':
        worker=ident(d.get('worker'));now=number(d.get('now'));lease=number(d.get('lease'),1)
        for r in s['runs'].values():
            if r['status']!='active':continue
            for n in r['nodes'].values():
                if n['status']=='running'and now>=n['expires']:
                    n['error']='Lease expired';n['status']='ready'if n['attempt']<n['max_attempts']else'failed';n['not_before']=n['expires']+n['retry_delay'];n.pop('receipt',None)
            refresh(r)
        for rid,r in sorted(s['runs'].items()):
            if r['status']!='active':continue
            for nid,n in sorted(r['nodes'].items()):
                if n['status']=='ready'and n['not_before']<=now:
                    s['receipts']+=1;n['attempt']+=1;n['status']='running';n['receipt']=f"claim-{s['receipts']}";n['expires']=now+lease
                    return {'run':rid,'node':nid,'attempt':n['attempt'],'receipt':n['receipt'],'expires':n['expires']}
        return None
    if op in('job.succeed','job.fail'):
        r,n,now=current()
        if op=='job.succeed':
            if 'result'not in d:raise ValueError('Result required')
            n['status']='succeeded';n['result']=copy.deepcopy(d['result'])
        else:
            error=ident(d.get('error'));n['error']=error;n['status']='ready'if n['attempt']<n['max_attempts']else'failed';n['not_before']=now+n['retry_delay']
        n.pop('receipt',None);refresh(r);return snapshot(r)
    if op=='run.cancel':
        r=run(d.get('id'))
        if r['status']=='cancelled':return snapshot(r)
        if r['status']in('succeeded','failed'):raise ValueError('Already terminal')
        for n in r['nodes'].values():
            if n['status']not in TERMINAL:n['status']='cancelled';n.pop('receipt',None)
        r['status']='cancelled';return snapshot(r)
    if op=='artifact.put':
        r,n,now=current();name=ident(d.get('name'));content=d.get('content')
        if not isinstance(content,str):raise ValueError('Content must be text')
        digest=hashlib.sha256(content.encode()).hexdigest();s['blobs'][digest]=content;n['attachments'][name]=digest;return {'digest':digest,'size':len(content.encode())}
    if op=='artifact.get':
        r=run(d.get('run'));nid=ident(d.get('node'));name=ident(d.get('name'));n=r['nodes'].get(nid)
        if not n or name not in n['attachments']:raise ValueError('Missing artifact')
        digest=n['attachments'][name];content=s['blobs'][digest];return {'digest':digest,'size':len(content.encode()),'content':content}
    if op=='run.delete':
        rid=ident(d.get('id'));r=run(rid)
        if r['status']=='active':raise ValueError('Run is active')
        del s['runs'][rid];s['keys']={key:v for key,v in s['keys'].items()if v['request']['id']!=rid};return {'deleted':True}
    if op=='artifact.gc':
        used={v for r in s['runs'].values()for n in r['nodes'].values()for v in n['attachments'].values()};old=len(s['blobs']);s['blobs']={k:v for k,v in s['blobs'].items()if k in used};return {'removed':old-len(s['blobs']),'remaining':len(s['blobs'])}
    if op=='schedule.put':
        sid=ident(d.get('id'));wid=ident(d.get('workflow'))
        if wid not in s['workflows']:raise ValueError('Missing workflow')
        value={'id':sid,'workflow':wid,'start':number(d.get('start')),'interval':number(d.get('interval'),1),'limit':number(d.get('limit'),1),'emitted':0}
        if sid in s['schedules']:
            old=s['schedules'][sid]
            if any(old[k]!=v for k,v in value.items()if k!='emitted'):raise ValueError('Schedule conflict')
            return old
        s['schedules'][sid]=value;return value
    if op=='schedule.get':
        sid=ident(d.get('id'))
        if sid not in s['schedules']:raise ValueError('Missing schedule')
        return s['schedules'][sid]
    if op=='schedule.tick':
        now=number(d.get('now'));limit=number(d.get('max_runs'),1,100);due=[]
        for sid,sch in s['schedules'].items():
            for k in range(sch['emitted'],sch['limit']):
                at=sch['start']+k*sch['interval']
                if at>now:break
                due.append((at,sid,k))
        selected=sorted(due)[:limit]
        if any('@'+sid+':'+str(k)in s['runs']for at,sid,k in selected):raise ValueError('Scheduled run ID conflict')
        result=[]
        for at,sid,k in selected:
            sch=s['schedules'][sid];result.append(snapshot(new_run(s,sch['workflow'],'@'+sid+':'+str(k))));sch['emitted']+=1
        return result
    if op=='run.list':
        status=d.get('status');after=d.get('after');limit=number(d.get('limit',20),1,100)
        if status is not None and status not in('active','succeeded','failed','cancelled'):raise ValueError('Invalid status')
        if after is not None:ident(after)
        values=[snapshot(r)for rid,r in sorted(s['runs'].items())if(after is None or rid>after)and(status is None or r['status']==status)]
        return {'items':values[:limit],'next':values[limit-1]['id']if len(values)>limit else None}
    raise ValueError('Unknown operation')
