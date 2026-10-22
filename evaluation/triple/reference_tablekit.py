import copy,csv,io,re
from decimal import Decimal,localcontext
from functools import cmp_to_key


def table(t):
    if not isinstance(t,dict)or set(t)!={'columns','rows'}:raise ValueError('table schema')
    cols,rows=t['columns'],t['rows']
    if not isinstance(cols,list)or not cols or any(not isinstance(x,str)or not x for x in cols)or len(set(cols))!=len(cols):raise ValueError('columns')
    if not isinstance(rows,list)or any(not isinstance(r,list)or len(r)!=len(cols)or any(x is not None and not isinstance(x,str) for x in r)for r in rows):raise ValueError('rows')
    return cols,rows

def read_csv(text):
    try:
        if not isinstance(text,str):raise ValueError('CSV text')
        rows=list(csv.reader(io.StringIO(text,newline=''),strict=True))
        if not rows:raise ValueError('empty CSV')
        def cell(x):return x[1:]if x.startswith('\\\\')else None if x=='\\N'else x
        out={'columns':rows[0],'rows':[[cell(x)for x in row]for row in rows[1:]]};table(out);return out
    except (csv.Error,TypeError)as e:raise ValueError('CSV')from e

def write_csv(t):
    columns,rows=table(t);out=io.StringIO(newline='');writer=csv.writer(out,lineterminator='\n');writer.writerow(columns)
    writer.writerows([['\\N'if x is None else '\\'+x if x.startswith('\\')else x for x in r]for r in rows]);return out.getvalue()

def number(x):
    if type(x)is int:return Decimal(x)
    if not isinstance(x,str)or not re.fullmatch(r'[+-]?\d+(?:\.\d+)?',x):raise ValueError('numeric')
    return Decimal(x)

def canonical(x):
    text=format(x,'f')
    if '.'in text:text=text.rstrip('0').rstrip('.')
    return '0'if x==0 else text

def execute(plan,tables):
    if not isinstance(plan,dict)or set(plan)-{'source','joins','where','group_by','aggregates','select','order_by','limit'}:raise ValueError('plan')
    if not isinstance(tables,dict)or any(not isinstance(k,str)or not k.strip()for k in tables):raise ValueError('tables')
    for value in tables.values():table(value)
    try:cols,values=table(tables[plan['source']])
    except (KeyError,TypeError)as e:raise ValueError('source')from e
    cols=list(cols);rows=[dict(zip(cols,r))for r in values]
    def fields(x,allowed,required):
        if not isinstance(x,dict)or set(x)-set(allowed)or not set(required)<=set(x):raise ValueError('fields')
    def columns(xs,available,nonempty=False):
        if not isinstance(xs,list)or nonempty and not xs or any(not isinstance(x,str)or x not in available for x in xs)or len(set(xs))!=len(xs):raise ValueError('column list')
    def array(key):
        x=plan.get(key,[])
        if not isinstance(x,list):raise ValueError(key)
        return x
    prefixes=set()
    for join in array('joins'):
        fields(join,['table','left_on','right_on','kind','prefix'],['table','left_on','right_on','kind','prefix'])
        try:rightcols,rightrows=table(tables[join['table']])
        except (KeyError,TypeError)as e:raise ValueError('join table')from e
        columns(join['left_on'],cols,True);columns(join['right_on'],rightcols,True)
        prefix=join['prefix']
        if len(join['left_on'])!=len(join['right_on'])or join['kind']not in ('inner','left')or not isinstance(prefix,str)or not prefix.strip()or prefix in prefixes:raise ValueError('join')
        added=[prefix+'.'+c for c in rightcols]
        if set(added)&set(cols):raise ValueError('collision')
        prefixes.add(prefix);out=[]
        rights=[dict(zip(rightcols,r))for r in rightrows]
        for left in rows:
            key=[left[c]for c in join['left_on']]
            matches=[r for r in rights if None not in key and all(r[b]is not None and a==r[b]for a,b in zip(key,join['right_on']))]
            for right in matches:out.append({**left,**{prefix+'.'+c:right[c]for c in rightcols}})
            if not matches and join['kind']=='left':out.append({**left,**dict.fromkeys(added)})
        rows=out;cols+=added
    for p in array('where'):
        fields(p,['column','op','value'],['column','op']);op=p['op']
        if p['column']not in cols or op not in ('eq','ne','lt','le','gt','ge','in','not_in','is_null','not_null'):raise ValueError('predicate')
        if op in ('is_null','not_null'):
            if 'value'in p:raise ValueError('predicate value')
        elif 'value'not in p:raise ValueError('value required')
        elif op in ('in','not_in'):
            if not isinstance(p['value'],list)or any(x is not None and not isinstance(x,str)for x in p['value']):raise ValueError('set')
        elif p['value']is not None and not isinstance(p['value'],str):raise ValueError('value')
        def matches(row):
            a=row[p['column']];b=p.get('value')
            if op=='is_null':return a is None
            if op=='not_null':return a is not None
            if a is None:return False
            if op=='in':return a in b
            if op=='not_in':return None not in b and a not in b
            if b is None:return False
            return {'eq':lambda:a==b,'ne':lambda:a!=b,'lt':lambda:a<b,'le':lambda:a<=b,'gt':lambda:a>b,'ge':lambda:a>=b}[op]()
        rows=[r for r in rows if matches(r)]
    keys=plan.get('group_by',[]);columns(keys,cols)
    aggs=array('aggregates');names=set(keys)
    for a in aggs:
        fields(a,['as','op','column'],['as','op','column'])
        if not isinstance(a['as'],str)or not a['as']or a['as']in names or a['op']not in ('count','sum','min','max')or not(a['column']in cols or a['column']=='*'and a['op']=='count'):raise ValueError('aggregate')
        names.add(a['as'])
    if keys or aggs:
        groups={}
        for row in rows:groups.setdefault(tuple(row[k]for k in keys),[]).append(row)
        if not keys and not rows:groups[()]=[]
        out=[]
        for key,group in groups.items():
            row=dict(zip(keys,key))
            for a in aggs:
                vals=[r[a['column']]for r in group if r[a['column']]is not None]if a['column']!='*'else group
                if a['op']=='count':v=len(vals)
                elif not vals:v=None
                elif a['op']=='sum':
                    numbers=[number(v)for v in vals]
                    with localcontext()as ctx:
                        ctx.prec=max(100,sum(len(v.as_tuple().digits)+abs(v.as_tuple().exponent)for v in numbers)+10)
                        v=canonical(sum(numbers,Decimal(0)))
                else:v=(min if a['op']=='min'else max)(vals)
                row[a['as']]=v
            out.append(row)
        rows=out;cols=keys+[a['as']for a in aggs]
    orders=array('order_by')
    for order in orders:
        fields(order,['column','descending','nulls','numeric'],['column'])
        if order['column']not in cols or type(order.get('descending',False))is not bool or type(order.get('numeric',False))is not bool or order.get('nulls','last')not in ('first','last'):raise ValueError('order')
        if order.get('numeric',False):
            for row in rows:
                if row[order['column']]is not None:number(row[order['column']])
    def cmp(a,b):
        for order in orders:
            x,y=a[order['column']],b[order['column']]
            if x is None or y is None:
                v=0 if x is y else (-1 if x is None else 1)*(1 if order.get('nulls','last')=='first'else -1)
            else:
                if order.get('numeric',False):x,y=number(x),number(y)
                v=((x>y)-(x<y))*(-1 if order.get('descending',False)else 1)
            if v:return v
        return 0
    rows=sorted(rows,key=cmp_to_key(cmp))
    selected=plan.get('select',cols);columns(selected,cols,True)
    limit=plan.get('limit',len(rows))
    if type(limit)is not int or limit<0:raise ValueError('limit')
    return {'columns':list(selected),'rows':[[r[c]for c in selected]for r in rows[:limit]]}
