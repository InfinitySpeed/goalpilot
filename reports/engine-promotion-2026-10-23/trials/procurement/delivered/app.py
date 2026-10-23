from goalpilot_runtime import ReplayService, require, fields, text, integer, choice, sequence, get_record, compare_revision, idempotent


def banner():return 'Local Ops — café'


def positive(v): return integer(v,minimum=1)

def create_fields(v):
    fields(v,dict(id=text,creator=text,amount=positive,approvals=positive))
    return v


class Service(ReplayService):
    def initial(self):
        return dict(departments={},members={},requests={},keys={})

    def report(self,s,department):
        budget=get_record(s['departments'],department)['budget']
        rows=[r for r in s['requests'].values() if r['department']==department]
        committed=sum(r['amount'] for r in rows if r['status']=='approved')
        spent=sum(r['amount']-r['refunded'] for r in rows if r['status']=='spent')
        return dict(budget=budget,committed=committed,spent=spent,available=budget-committed-spent)

    def create(self,s,d):
        create_fields(d)
        require(d['id'] not in s['requests'],'Duplicate request')
        member=get_record(s['members'],d['creator'])
        r=dict(d,department=member['department'],approved=[],status='pending',revision=1,refunded=0)
        s['requests'][d['id']]=r
        return r

    def handle(self,s,op,d):
        if op=='department.put':
            fields(d,dict(id=text,budget=integer))
            if d['id'] in s['departments']:
                old=self.report(s,d['id']); require(d['budget']>=old['committed']+old['spent'],'Budget below obligations')
            s['departments'][d['id']]={'budget':d['budget']}
            return dict(d)
        if op=='member.put':
            fields(d,dict(id=text,department=text,role=choice('requester','approver')))
            get_record(s['departments'],d['department'])
            for r in s['requests'].values():
                if r['status']=='pending':
                    if r['creator']==d['id']: require(d['department']==r['department'],'Pending creator department')
                    if d['id'] in r['approved']: require(d['department']==r['department'] and d['role']=='approver','Pending approval invalidated')
            s['members'][d['id']]=dict(d)
            return dict(d)
        if op=='request.create': return self.create(s,d)
        if op=='request.import':
            fields(d,dict(requests=sequence(create_fields)))
            for row in d['requests']: self.create(s,row)
            return {'imported':len(d['requests'])}
        if op=='department.report':
            fields(d,dict(id=text)); return self.report(s,d['id'])
        if op=='request.get':
            fields(d,dict(id=text)); return get_record(s['requests'],d['id'])
        if op in ('request.approve','request.reject'):
            fields(d,dict(id=text,actor=text,expected_revision=positive))
            r=get_record(s['requests'],d['id']); compare_revision(r,d['expected_revision'])
            require(r['status'] in (('pending',) if op=='request.approve' else ('pending','approved')),'Invalid status')
            actor=get_record(s['members'],d['actor'])
            require(actor['role']=='approver' and actor['department']==r['department'] and d['actor']!=r['creator'],'Unauthorized actor')
            if op=='request.approve':
                require(d['actor'] not in r['approved'],'Already approved')
                if len(r['approved'])+1==r['approvals']:
                    require(self.report(s,r['department'])['available']>=r['amount'],'Insufficient budget')
                    r['status']='approved'
                r['approved']=sorted(r['approved']+[d['actor']])
            else: r['status']='rejected'
            r['revision']+=1
            return r
        if op in ('request.spend','request.refund'):
            schema=dict(id=text,key=text)
            if op=='request.refund': schema['amount']=positive
            fields(d,schema)
            def apply():
                r=get_record(s['requests'],d['id'])
                require(r['status']==('approved' if op=='request.spend' else 'spent'),'Invalid status')
                if op=='request.spend': r['status']='spent'
                else:
                    require(d['amount']<=r['amount']-r['refunded'],'Excess refund')
                    r['refunded']+=d['amount']
                r['revision']+=1
                return r
            return idempotent(s,d['key'],op,dict(d),apply)
        raise ValueError('Unknown operation')


if __name__=='__main__': Service.main()
