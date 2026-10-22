import copy,csv,io,json
APPLICATION='flowdesk'
def initial():return {'workspaces':{},'tokens':{},'receipts':0}
def ident(x):
    if not isinstance(x,str)or not x:raise ValueError('Expected nonempty ID/text')
    return x
def number(x,lo=0,hi=None):
    if type(x)is not int or x<lo or hi is not None and x>hi:raise ValueError('Invalid integer')
    return x
def tags(x):
    if not isinstance(x,list):raise ValueError('Expected tag list')
    return sorted(set(ident(t)for t in x))
def ticket_value(d):return {'id':ident(d.get('id')),'title':ident(d.get('title')),'tags':tags(d.get('tags',[])),'status':'open','revision':1}
def validate_state(s):
    try:
        assert isinstance(s,dict)and isinstance(s['workspaces'],dict)and isinstance(s['tokens'],dict);number(s['receipts'])
        for wid,w in s['workspaces'].items():
            ident(wid);assert isinstance(w['keys'],dict)and isinstance(w['claims'],dict)
            assert isinstance(w['members'],dict)and any(v=='admin'for v in w['members'].values())
            for token,role in w['members'].items():assert role in ('admin','agent','viewer')and s['tokens'][token]==wid
            for tid,t in w['tickets'].items():
                assert tid==t['id'];ticket_value(t);assert t['status']in('open','pending','closed');number(t['revision'],1)
            for tid,items in w['comments'].items():
                assert tid in w['tickets']and isinstance(items,list);seen=set()
                for c in items:
                    ident(c['id']);ident(c['text']);assert type(c['internal'])is bool and c['id']not in seen;seen.add(c['id'])
            last=0
            for e in w['audit']:
                number(e['sequence'],1);assert e['sequence']>last;last=e['sequence'];assert e['kind']in('ticket.created','ticket.changed','ticket.deleted','comment.added');ident(e['ticket']);assert isinstance(e['snapshot'],dict)
            for seq,c in w['claims'].items():
                assert int(seq)in{e['sequence']for e in w['audit']};assert type(c['acked'])is bool;ident(c['receipt']);number(c['expires'])
        for token,wid in s['tokens'].items():ident(token);assert token in s['workspaces'][wid]['members']
    except (AssertionError,KeyError,TypeError,AttributeError,ValueError)as exc:raise ValueError('Invalid domain backup')from exc

def handle(s,op,d):
    wid=ident(d.get('workspace'));token=ident(d.get('token'))
    if op=='bootstrap':
        if wid in s['workspaces']:
            if s['workspaces'][wid]['members'].get(token)!='admin':raise ValueError('Workspace exists')
            return {'workspace':wid}
        if token in s['tokens']:raise ValueError('Token belongs to another workspace')
        s['tokens'][token]=wid;s['workspaces'][wid]={'members':{token:'admin'},'tickets':{},'comments':{},'audit':[],'claims':{},'keys':{}}
        return {'workspace':wid}
    if s['tokens'].get(token)!=wid or wid not in s['workspaces']:raise ValueError('Access denied')
    w=s['workspaces'][wid];role=w['members'][token]
    def admin():
        if role!='admin':raise ValueError('Admin required')
    def write():
        if role=='viewer':raise ValueError('Read only')
    def get(tid):
        ident(tid)
        if tid not in w['tickets']:raise ValueError('Missing ticket')
        return w['tickets'][tid]
    def event(kind,tid,snapshot):
        seq=w['audit'][-1]['sequence']+1 if w['audit'] else 1
        w['audit'].append({'sequence':seq,'kind':kind,'ticket':tid,'snapshot':copy.deepcopy(snapshot)})
    def create(t):
        if t['id']in w['tickets']:raise ValueError('Duplicate ticket')
        w['tickets'][t['id']]=copy.deepcopy(t);w['comments'][t['id']]=[];event('ticket.created',t['id'],t);return t
    if op=='member.add':
        admin();new=ident(d.get('new_token'));r=d.get('role')
        if r not in('admin','agent','viewer')or new in s['tokens']:raise ValueError('Invalid role or duplicate identity')
        s['tokens'][new]=wid;w['members'][new]=r;return {'role':r}
    if op=='ticket.create':
        write();t=ticket_value(d);key=d.get('idempotency_key');marker=None
        if key is not None:
            ident(key);marker=json.dumps([token,key])
            if marker in w['keys']:
                old=w['keys'][marker]
                if old['request']!=t:raise ValueError('Idempotency conflict')
                return old['result']
        result=create(t)
        if marker is not None:w['keys'][marker]={'request':copy.deepcopy(t),'result':copy.deepcopy(result)}
        return result
    if op=='ticket.get':return get(d.get('id'))
    if op=='ticket.change':
        write();t=get(d.get('id'));revision=number(d.get('expected_revision'),1)
        if t['revision']!=revision:raise ValueError('Revision conflict')
        changes={}
        if 'title'in d:changes['title']=ident(d['title'])
        if 'tags'in d:changes['tags']=tags(d['tags'])
        status=d.get('status',t['status'])
        allowed={'open':{'open','pending','closed'},'pending':{'pending','open','closed'},'closed':{'closed','open'}}
        if status not in allowed[t['status']]:raise ValueError('Invalid transition')
        t.update(changes);t['status']=status;t['revision']+=1;event('ticket.changed',t['id'],t);return t
    if op=='ticket.delete':
        admin();t=get(d.get('id'));rev=number(d.get('expected_revision'),1)
        if rev!=t['revision']:raise ValueError('Revision conflict')
        event('ticket.deleted',t['id'],t);del w['tickets'][t['id']];w['comments'].pop(t['id'],None);return {'deleted':True}
    if op=='comment.add':
        write();t=get(d.get('ticket'));cid=ident(d.get('id'));text=ident(d.get('text'));internal=d.get('internal',False)
        if type(internal)is not bool or any(c['id']==cid for c in w['comments'][t['id']]):raise ValueError('Invalid comment')
        c={'id':cid,'text':text,'internal':internal};w['comments'][t['id']].append(c);event('comment.added',t['id'],c);return c
    if op=='comment.list':
        t=get(d.get('ticket'));return[c for c in w['comments'][t['id']]if not c['internal']or role!='viewer']
    if op=='ticket.list':
        lim=number(d.get('limit',20),1,100);status=d.get('status');tag=d.get('tag');after=d.get('after')
        if status is not None and status not in('open','pending','closed'):raise ValueError('Invalid status')
        if tag is not None:ident(tag)
        if after is not None:ident(after)
        values=[t for key,t in sorted(w['tickets'].items())if(after is None or key>after)and(status is None or t['status']==status)and(tag is None or tag in t['tags'])]
        selected=values[:lim];return {'items':selected,'next':selected[-1]['id']if len(values)>lim else None}
    if op=='ticket.import':
        admin();text=d.get('csv')
        if not isinstance(text,str):raise ValueError('Expected CSV')
        try:
            rows=list(csv.reader(io.StringIO(text),strict=True))
            if not rows or rows[0]!=['id','title','tags']:raise ValueError('Invalid header')
            values=[];seen=set(w['tickets'])
            for row in rows[1:]:
                if len(row)!=3:raise ValueError('Invalid CSV row')
                t=ticket_value({'id':row[0],'title':row[1],'tags':json.loads(row[2])})
                if t['id']in seen:raise ValueError('Duplicate ID')
                seen.add(t['id']);values.append(t)
        except (csv.Error,json.JSONDecodeError,TypeError)as exc:raise ValueError('Invalid CSV')from exc
        for t in values:create(t)
        return {'imported':len(values)}
    if op=='ticket.export':
        stream=io.StringIO(newline='');writer=csv.writer(stream);writer.writerow(['id','title','tags'])
        for tid,t in sorted(w['tickets'].items()):writer.writerow([tid,t['title'],json.dumps(t['tags'],ensure_ascii=False)])
        return stream.getvalue()
    if op=='audit.list':admin();return w['audit']
    if op=='event.claim':
        admin();worker=ident(d.get('worker'));now=number(d.get('now'));lease=number(d.get('lease'),1);limit=number(d.get('limit'),1,100);result=[]
        for e in w['audit']:
            c=w['claims'].get(str(e['sequence']))
            if c and(c['acked']or c['expires']>now):continue
            s['receipts']+=1;receipt=f"receipt-{s['receipts']}";w['claims'][str(e['sequence'])]={'receipt':receipt,'acked':False,'expires':now+lease}
            result.append({'sequence':e['sequence'],'receipt':receipt,'event':e})
            if len(result)>=limit:break
        return result
    if op=='event.ack':
        admin();seq=number(d.get('sequence'),1);receipt=ident(d.get('receipt'));c=w['claims'].get(str(seq))
        if not c or c['acked']or c['receipt']!=receipt:raise ValueError('Invalid receipt')
        c['acked']=True;return {'acked':True}
    raise ValueError('Unknown operation')
