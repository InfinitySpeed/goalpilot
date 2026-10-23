from copy import deepcopy
from goalpilot_runtime import ReplayService, require, text, integer, fields, mapping, sequence, get_record, compare_revision


def banner():return 'Local Ops — café'


strings = mapping(lambda v: require(isinstance(v, str), 'Expected string'))
def content(v):
    strings(v)
    require(bool(v) and all(isinstance(k,str) and k for k in v), 'Expected nonempty fields')


class Service(ReplayService):
    def initial(self):return {'documents':{}, 'branches':{}}

    def handle(self,s,op,d):
        docs, branches = s['documents'], s['branches']
        def document():return get_record(docs,d['id'])
        def public(r):return {k:deepcopy(v) for k,v in r.items() if k not in ('history','base')}
        def edit(r,changes):
            r['fields'].update(changes); r['revision']+=1
            r['approved']=[]; r['status']='draft'
        if op in ('document.create','document.import'):
            if op=='document.create':
                fields(d,{'id':text,'fields':content}); rows=[d]
            else:
                fields(d,{'documents':sequence(lambda x:fields(x,{'id':text,'fields':content}))}); rows=d['documents']
            require(len({r['id'] for r in rows})==len(rows),'Duplicate document')
            require(all(r['id'] not in docs for r in rows),'Document exists')
            for r in rows:
                docs[r['id']]={'id':r['id'],'revision':1,'fields':deepcopy(r['fields']),'status':'draft','approved':[],'published':0,'history':{}}
            return public(docs[d['id']]) if op=='document.create' else {'imported':len(rows)}
        if op=='document.list':
            fields(d,{}); return [public(docs[k]) for k in sorted(docs)]
        if op in ('document.get','document.live','branch.get'):
            fields(d,{'id':text})
            r=get_record(branches if op=='branch.get' else docs,d['id'])
            if op=='document.live':
                require(r['published']>0,'Never published')
                return {'id':r['id'],'revision':r['published'],'fields':deepcopy(r['history'][str(r['published'])])}
            return public(r)
        if op=='branch.create':
            fields(d,{'id':text,'document':text}); require(d['id'] not in branches,'Branch exists')
            r=get_record(docs,d['document'])
            b={'id':d['id'],'document':d['document'],'base_revision':r['revision'],'revision':1,'fields':deepcopy(r['fields']),'base':deepcopy(r['fields']),'status':'open'}
            branches[d['id']]=b; return public(b)
        if op in ('document.edit','branch.edit'):
            fields(d,{'id':text,'expected_revision':lambda x:integer(x,minimum=1),'changes':content})
            r=get_record(branches if op=='branch.edit' else docs,d['id']); compare_revision(r,d['expected_revision'])
            if op=='branch.edit':
                require(r['status']=='open','Branch closed'); r['fields'].update(d['changes']); r['revision']+=1
            else:edit(r,d['changes'])
            return public(r)
        if op=='branch.merge':
            fields(d,{'id':text,'expected_revision':lambda x:integer(x,minimum=1),'document_revision':lambda x:integer(x,minimum=1)})
            b=get_record(branches,d['id']); compare_revision(b,d['expected_revision']); require(b['status']=='open','Branch closed')
            r=get_record(docs,b['document']); compare_revision(r,d['document_revision'])
            changes={k:v for k,v in b['fields'].items() if k not in b['base'] or b['base'][k]!=v}
            for k,v in changes.items():
                require((k in r['fields'])==(k in b['base']) and r['fields'].get(k)==b['base'].get(k) or r['fields'].get(k)==v,'Merge conflict')
            edit(r,changes); b['status']='merged'; b['revision']+=1
            return public(r)
        if op in ('document.approve','document.publish'):
            schema={'id':text,'expected_revision':lambda x:integer(x,minimum=1)}
            if op=='document.approve':schema['actor']=text
            fields(d,schema); r=document(); compare_revision(r,d['expected_revision'])
            if op=='document.approve':
                require(r['status'] in ('draft','approved'),'Cannot approve published document')
                r['approved']=sorted(set(r['approved']+[d['actor']]))
                r['status']='approved' if len(r['approved'])>=2 else 'draft'
            else:
                require(r['status']=='approved','Two approvals required')
                r['history'][str(r['revision'])]=deepcopy(r['fields']); r['published']=r['revision']; r['status']='published'
            return public(r)
        raise ValueError('Unknown operation')


if __name__=='__main__':Service.main()
