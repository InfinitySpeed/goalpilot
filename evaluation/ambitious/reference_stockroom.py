import copy,json
APPLICATION='stockroom'
def initial():return {'products':{},'warehouses':[],'balances':{},'orders':{},'purchases':{},'movements':[],'keys':{}}
def ident(x):
    if not isinstance(x,str)or not x:raise ValueError('Expected nonempty ID/text')
    return x
def number(x,lo=0):
    if type(x)is not int or x<lo:raise ValueError('Invalid integer')
    return x
def lines(values,warehouse=False):
    if not isinstance(values,list)or not values:raise ValueError('Expected nonempty lines')
    counts={}
    for row in values:
        if not isinstance(row,dict):raise ValueError('Invalid line')
        key=(ident(row.get('sku')),ident(row.get('warehouse')))if warehouse else(ident(row.get('sku')),)
        counts[key]=counts.get(key,0)+number(row.get('quantity'),1)
    return[dict(zip(['sku','warehouse']if warehouse else['sku'],key),quantity=counts[key])for key in sorted(counts)]
def mapping(rows):return{(r['sku'],r.get('warehouse')):r['quantity']for r in rows}
def cumulative(old,new):
    counts=mapping(old)
    for r in new:
        key=(r['sku'],r.get('warehouse'));counts[key]=counts.get(key,0)+r['quantity']
    return[dict(sku=key[0],**({'warehouse':key[1]}if key[1]is not None else{}),quantity=q)for key,q in sorted(counts.items())]
def validate_state(s):
    try:
        assert isinstance(s,dict)
        for key in('products','balances','orders','purchases','keys'):assert isinstance(s[key],dict)
        assert isinstance(s['warehouses'],list)and len(s['warehouses'])==len(set(s['warehouses']))
        for wid in s['warehouses']:ident(wid)
        for sku,p in s['products'].items():assert sku==p['sku'];ident(sku);ident(p['name']);number(p['reorder_point'])
        required={}
        for oid,o in s['orders'].items():
            assert oid==o['id']and o['status']in('draft','confirmed','partial','shipped','cancelled');assert lines(o['lines'])==o['lines']
            for line in o['lines']:assert line['sku']in s['products']
            allocated=mapping(o['allocations']);shipped=mapping(o['shipped']);returned=mapping(o['returned'])
            for values in(o['allocations'],o['shipped'],o['returned']):
                if values:assert lines(values,True)==values
                for r in values:assert r['sku']in s['products']and r['warehouse']in s['warehouses']
            assert all(v<=allocated.get(k,0)for k,v in shipped.items())and all(v<=shipped.get(k,0)for k,v in returned.items())
            if o['status']=='shipped':assert allocated and allocated==shipped
            if o['status']=='draft':assert not allocated and not shipped and not returned
            if o['status']in('confirmed','partial'):
                for k,q in allocated.items():required[k]=required.get(k,0)+q-shipped.get(k,0)
        for sku,warehouses in s['balances'].items():
            assert sku in s['products']and isinstance(warehouses,dict)
            for wid,b in warehouses.items():
                assert wid in s['warehouses'];number(b['on_hand']);number(b['reserved']);assert b['reserved']<=b['on_hand']and b['reserved']==required.pop((sku,wid),0)
        assert not any(required.values())
        for pid,p in s['purchases'].items():
            assert pid==p['id']and p['warehouse']in s['warehouses']and p['status']in('open','partial','received');assert lines(p['lines'])==p['lines']
            requested=mapping(p['lines']);got=mapping(p['received'])
            assert all(v<=requested.get(k,0)for k,v in got.items())
            for r in p['lines']:assert r['sku']in s['products']
        last=0
        for m in s['movements']:number(m['sequence'],1);assert m['sequence']>last;last=m['sequence'];assert m['sku']in s['products']and m['warehouse']in s['warehouses']and type(m['delta'])is int
    except (AssertionError,KeyError,TypeError,AttributeError,ValueError)as exc:raise ValueError('Invalid domain backup')from exc

def handle(s,op,d):
    def product(sku):
        ident(sku)
        if sku not in s['products']:raise ValueError('Unknown SKU')
        return s['products'][sku]
    def warehouse(wid):
        ident(wid)
        if wid not in s['warehouses']:raise ValueError('Unknown warehouse')
        return wid
    def balance(sku,wid):
        product(sku);warehouse(wid);return s['balances'].setdefault(sku,{}).setdefault(wid,{'on_hand':0,'reserved':0})
    def snap(b):return{**b,'available':b['on_hand']-b['reserved']}
    def move(kind,sku,wid,delta):s['movements'].append({'sequence':len(s['movements'])+1,'kind':kind,'sku':sku,'warehouse':wid,'delta':delta})
    def find(which,oid):
        ident(oid)
        if oid not in s[which]:raise ValueError('Missing record')
        return s[which][oid]
    def known(rows):
        for row in rows:
            product(row['sku'])
            if 'warehouse'in row:warehouse(row['warehouse'])
    key=None;request=None
    if op in('stock.receive','stock.transfer','stock.count','order.ship','order.return','purchase.receive'):
        key=ident(d.get('key'))
        request={k:v for k,v in d.items()if k!='key'}
        if 'lines'in request:request['lines']=lines(request['lines'],op in('order.ship','order.return'))
        if key in s['keys']:
            old=s['keys'][key]
            if old['operation']!=op or old['request']!=request:raise ValueError('Idempotency conflict')
            return old['result']
        d={**request,'key':key}
    result=None
    if op=='product.put':
        sku=ident(d.get('sku'));p={'sku':sku,'name':ident(d.get('name')),'reorder_point':number(d.get('reorder_point',0))};s['products'][sku]=p;return p
    elif op=='warehouse.add':
        wid=ident(d.get('id'))
        if wid not in s['warehouses']:s['warehouses'].append(wid);s['warehouses'].sort()
        return {'id':wid}
    elif op=='catalog':return[s['products'][k]for k in sorted(s['products'])]
    elif op=='stock.get':return snap(balance(d.get('sku'),d.get('warehouse')))
    elif op=='stock.receive':
        sku=ident(d.get('sku'));wid=ident(d.get('warehouse'));qty=number(d.get('quantity'),1);b=balance(sku,wid);b['on_hand']+=qty;move('receive',sku,wid,qty);result={'on_hand':b['on_hand']}
    elif op=='movement.list':
        sku=d.get('sku')
        if sku is not None:product(sku)
        return[m for m in s['movements']if sku is None or m['sku']==sku]
    elif op=='reorder':return[sku for sku,p in sorted(s['products'].items())if sum(b['on_hand']-b['reserved']for b in s['balances'].get(sku,{}).values())<p['reorder_point']]
    elif op in('order.create','purchase.create'):
        which='orders'if op=='order.create'else'purchases';oid=ident(d.get('id'));rows=lines(d.get('lines'));known(rows)
        if oid in s[which]:raise ValueError('Duplicate record')
        if which=='orders':o={'id':oid,'lines':rows,'status':'draft','allocations':[],'shipped':[],'returned':[]}
        else:o={'id':oid,'warehouse':warehouse(d.get('warehouse')),'lines':rows,'status':'open','received':[]}
        s[which][oid]=o;return o
    elif op in('order.get','purchase.get'):return find('orders'if op=='order.get'else'purchases',d.get('id'))
    elif op=='order.confirm':
        o=find('orders',d.get('id'))
        if o['status']=='confirmed':return o
        if o['status']!='draft':raise ValueError('Order not draft')
        allocations=[]
        for row in o['lines']:
            remaining=row['quantity']
            for wid in sorted(s['warehouses']):
                b=balance(row['sku'],wid);q=min(remaining,b['on_hand']-b['reserved'])
                if q:allocations.append({'sku':row['sku'],'warehouse':wid,'quantity':q});b['reserved']+=q;remaining-=q
                if not remaining:break
            if remaining:raise ValueError('Insufficient stock')
        o['allocations']=allocations;o['status']='confirmed';return o
    elif op=='order.cancel':
        o=find('orders',d.get('id'))
        if o['status']=='cancelled':return o
        if o['status']=='shipped':raise ValueError('Already shipped')
        sent=mapping(o['shipped'])
        for r in o['allocations']:balance(r['sku'],r['warehouse'])['reserved']-=r['quantity']-sent.get((r['sku'],r['warehouse']),0)
        o['status']='cancelled';return o
    elif op in('order.ship','order.return'):
        o=find('orders',d.get('id'));rows=d['lines'];known(rows);back=op=='order.return'
        if not back and o['status']not in('confirmed','partial'):raise ValueError('Order not shippable')
        capacity=mapping(o['shipped']if back else o['allocations']);used=mapping(o['returned']if back else o['shipped'])
        for r in rows:
            pair=(r['sku'],r['warehouse'])
            if r['quantity']>capacity.get(pair,0)-used.get(pair,0):raise ValueError('Quantity exceeds history')
        for r in rows:
            b=balance(r['sku'],r['warehouse']);q=r['quantity'];b['on_hand']+=q if back else-q
            if not back:b['reserved']-=q
            move('return'if back else'ship',r['sku'],r['warehouse'],q if back else-q)
        field='returned'if back else'shipped';o[field]=cumulative(o[field],rows)
        if not back:o['status']='shipped'if mapping(o['shipped'])==mapping(o['allocations'])else'partial'
        result=o
    elif op=='stock.transfer':
        sku=ident(d.get('sku'));src=warehouse(d.get('source'));dst=warehouse(d.get('target'));q=number(d.get('quantity'),1)
        if src==dst:raise ValueError('Same warehouse')
        left=balance(sku,src);right=balance(sku,dst)
        if q>left['on_hand']-left['reserved']:raise ValueError('Insufficient available stock')
        left['on_hand']-=q;right['on_hand']+=q;move('transfer',sku,src,-q);move('transfer',sku,dst,q);result={'source':snap(left),'target':snap(right)}
    elif op=='stock.count':
        sku=ident(d.get('sku'));wid=warehouse(d.get('warehouse'));expected=number(d.get('expected_on_hand'));new=number(d.get('new_on_hand'));b=balance(sku,wid)
        if b['on_hand']!=expected or new<b['reserved']:raise ValueError('Count conflict')
        delta=new-b['on_hand'];b['on_hand']=new;move('count',sku,wid,delta);result=snap(b)
    elif op=='purchase.receive':
        p=find('purchases',d.get('id'));rows=d['lines'];known(rows);requested=mapping(p['lines']);got=mapping(p['received'])
        for r in rows:
            pair=(r['sku'],None)
            if r['quantity']>requested.get(pair,0)-got.get(pair,0):raise ValueError('Invalid purchase receipt')
        for r in rows:balance(r['sku'],p['warehouse'])['on_hand']+=r['quantity'];move('receive',r['sku'],p['warehouse'],r['quantity'])
        p['received']=cumulative(p['received'],rows);p['status']='received'if mapping(p['received'])==requested else'partial';result=p
    else:raise ValueError('Unknown operation')
    if key is not None:s['keys'][key]={'operation':op,'request':copy.deepcopy(request),'result':copy.deepcopy(result)}
    return result
