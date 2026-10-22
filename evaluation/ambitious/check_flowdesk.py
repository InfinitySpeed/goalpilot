import copy,csv,io,json

def seed(s):
    s.call('bootstrap',{'workspace':'w','token':'a'});s.call('member.add',{'workspace':'w','token':'a','new_token':'v','role':'viewer'});s.call('member.add',{'workspace':'w','token':'a','new_token':'u','role':'agent'})
    def call(op,**kw):return s.call(op,{'workspace':'w','token':'a',**kw})
    return call

def check(s,group,rng,raises,repo):
    c=seed(s)
    def make(tid='t',**kw):return c('ticket.create',id=tid,title='Café, 東京\nIssue',tags=['red','red','blue'],**kw)
    if group=='journey':
        x=make(idempotency_key='key');assert x['tags']==['blue','red'];assert c('ticket.change',id='t',expected_revision=1,status='pending')['revision']==2
        c('comment.add',ticket='t',id='private',text='Secret',internal=True);c('comment.add',ticket='t',id='public',text='Reply')
        visible=c('comment.list',ticket='t',token='v');assert [v['id']for v in visible]==['public'];assert c('ticket.get',id='t')['revision']==2
        c('ticket.change',id='t',expected_revision=2,status='closed');raises(lambda:c('ticket.change',id='t',expected_revision=3,status='pending'))
        assert c('ticket.change',id='t',expected_revision=3,status='open')['revision']==4
        text=c('ticket.export');c('bootstrap',workspace='other',token='b');assert c('ticket.import',workspace='other',token='b',csv=text)['imported']==1
        assert c('ticket.get',workspace='other',token='b',id='t')['title']==x['title']
    elif group=='atomicity':
        make('existing');before=c('audit.list');text='id,title,tags\nnew,First,[]\nexisting,Second,[]\n'
        raises(lambda:c('ticket.import',csv=text));raises(lambda:c('ticket.get',id='new'));assert c('audit.list')==before
        raises(lambda:c('ticket.change',id='existing',expected_revision=1,title='Changed',tags=[3]));assert c('ticket.get',id='existing')['title']!='Changed';assert c('audit.list')==before
    elif group=='idempotency':
        first=make(idempotency_key='k');c('ticket.change',id='t',expected_revision=1,title='Now different')
        assert make(idempotency_key='k')==first;assert len(c('audit.list'))==2
        raises(lambda:c('ticket.create',id='t',title='Another',idempotency_key='k'))
        c('ticket.create',id='agent-ticket',title='Independent key',token='u',idempotency_key='k');assert len(c('audit.list'))==3
    elif group=='isolation_or_revision':
        make();c('bootstrap',workspace='z',token='z-admin');c('ticket.create',workspace='z',token='z-admin',id='t',title='Other tenant')
        for op,kw in [('ticket.get',{'id':'t'}),('ticket.list',{}),('ticket.export',{})]:raises(lambda op=op,kw=kw:c(op,workspace='z',**kw))
        raises(lambda:c('member.add',token='u',new_token='evil',role='admin'));raises(lambda:c('ticket.change',id='t',token='v',expected_revision=1,title='Bad'))
        for i in range(1,5):assert c('ticket.change',id='t',expected_revision=i)['revision']==i+1
        raises(lambda:c('ticket.change',id='t',expected_revision=4,title='Stale'));assert c('ticket.get',id='t')['revision']==5
    elif group=='pagination_or_schedule':
        for tid in ['a','b','c','d','e']:make(tid)
        c('ticket.change',id='b',expected_revision=1,status='closed');x=c('ticket.list',status='open',tag='red',limit=2);assert [r['id']for r in x['items']]==['a','c']and x['next']=='c'
        c('ticket.delete',id='c',expected_revision=1);make('aa');y=c('ticket.list',status='open',tag='red',after=x['next'],limit=2);assert [r['id']for r in y['items']]==['d','e']and y['next']is None
        assert c('ticket.list',status='pending')['items']==[]
        expected=[]
        for i in range(12):
            tid='prop'+str(i).zfill(2);tag=rng.choice(['red','green']);c('ticket.create',id=tid,title='Generated '+str(rng.randrange(9999)),tags=[tag])
            if tag=='green':expected.append(tid)
        got=[];after='prop'
        while True:
            page=c('ticket.list',tag='green',after=after,limit=3);got.extend(x['id']for x in page['items'])
            if page['next']is None:break
            after=page['next']
        assert got==expected
    elif group=='history_or_artifacts':
        first=make();c('comment.add',ticket='t',id='n',text='A note',internal=True);c('ticket.change',id='t',expected_revision=1,title='Second');c('ticket.delete',id='t',expected_revision=2);make()
        events=c('audit.list');assert [e['kind']for e in events]==['ticket.created','comment.added','ticket.changed','ticket.deleted','ticket.created']
        assert events[0]['snapshot']['title']==first['title'];assert events[2]['snapshot']['title']=='Second';assert events[1]['snapshot']['internal']is True
        assert len({e['sequence']for e in events})==5;assert c('comment.list',ticket='t')==[]
    elif group=='recovery_or_returns':
        make();c('ticket.change',id='t',expected_revision=1,title='Updated');first=c('event.claim',worker='one',now=10,lease=5,limit=1);assert len(first)==1
        rest=c('event.claim',worker='two',now=11,lease=5,limit=5);assert len(rest)==1 and rest[0]['sequence']!=first[0]['sequence']
        retry=c('event.claim',worker='three',now=15,lease=4,limit=5);assert [r['sequence']for r in retry]==[first[0]['sequence']]and retry[0]['receipt']!=first[0]['receipt']
        raises(lambda:c('event.ack',sequence=first[0]['sequence'],receipt=first[0]['receipt']));c('event.ack',sequence=retry[0]['sequence'],receipt=retry[0]['receipt']);c('event.ack',sequence=rest[0]['sequence'],receipt=rest[0]['receipt']);assert c('event.claim',worker='last',now=100,lease=1,limit=10)==[]
    elif group=='validation':
        make();before=c('audit.list')
        for op,kw in [('ticket.create',{'id':'bad','title':''}),('ticket.create',{'id':'bad','title':'x','tags':[False]}),('ticket.list',{'limit':True}),('event.claim',{'worker':'x','now':True,'lease':1,'limit':1}),('comment.add',{'ticket':'t','id':'bad','text':'x','internal':1})]:raises(lambda op=op,kw=kw:c(op,**kw))
        assert c('audit.list')==before
        assert 'token'not in c('ticket.get',id='t')
    return c
