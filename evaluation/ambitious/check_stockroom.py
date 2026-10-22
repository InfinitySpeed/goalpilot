from evaluation.ambitious.assertions import matches
import copy

def seed(s):
    def c(op,**kw):return s.call(op,kw)
    for sku in('x','y'):c('product.put',sku=sku,name='Product '+sku,reorder_point=2)
    for wid in('a','b'):c('warehouse.add',id=wid)
    return c

def check(s,group,rng,raises,repo):
    c=seed(s)
    def receive(sku='x',wid='a',q=10,key='r'):return c('stock.receive',sku=sku,warehouse=wid,quantity=q,key=key)
    def order(oid='o',q=6,sku='x'):return c('order.create',id=oid,lines=[{'sku':sku,'quantity':q}])
    def line(q=1,sku='x',wid='a'):return{'sku':sku,'warehouse':wid,'quantity':q}
    if group=='journey':
        c('purchase.create',id='p',warehouse='a',lines=[{'sku':'x','quantity':8}]);c('purchase.receive',id='p',lines=[{'sku':'x','quantity':3}],key='p1');assert c('purchase.receive',id='p',lines=[{'sku':'x','quantity':5}],key='p2')['status']=='received'
        order(q=6);c('order.confirm',id='o');assert matches(c('stock.get',sku='x',warehouse='a'),{'on_hand':8,'reserved':6,'available':2})
        assert c('order.ship',id='o',lines=[line(4)],key='ship')['status']=='partial';c('order.cancel',id='o');c('order.return',id='o',lines=[line(2)],key='back');assert matches(c('stock.get',sku='x',warehouse='a'),{'on_hand':6,'reserved':0,'available':6})
        assert matches(c('order.get',id='o')['returned'],[line(2)])
    elif group=='atomicity':
        receive(q=3);c('order.create',id='o',lines=[{'sku':'x','quantity':2},{'sku':'y','quantity':1}]);raises(lambda:c('order.confirm',id='o'));assert c('stock.get',sku='x',warehouse='a')['reserved']==0 and c('order.get',id='o')['status']=='draft'
        receive('y',q=1,key='y');c('order.confirm',id='o');before=c('movement.list');raises(lambda:c('order.ship',id='o',lines=[line(1),line(2,'y')],key='bad'));assert c('movement.list')==before and c('stock.get',sku='x',warehouse='a')['on_hand']==3
        assert c('order.ship',id='o',lines=[line(1)],key='bad')['status']=='partial'
    elif group=='idempotency':
        first=receive();c('stock.transfer',sku='x',source='a',target='b',quantity=2,key='move');assert receive()==first
        order(q=4);c('order.confirm',id='o');rows=[line(1),line(1)];first=c('order.ship',id='o',lines=rows,key='s');c('order.ship',id='o',lines=[line(2)],key='s2');assert c('order.ship',id='o',lines=[line(2)],key='s')==first
        raises(lambda:c('stock.receive',sku='x',warehouse='a',quantity=1,key='s'));assert len(c('movement.list'))==5
    elif group=='isolation_or_revision':
        receive();order(q=8);c('order.confirm',id='o');raises(lambda:c('stock.transfer',sku='x',source='a',target='b',quantity=3,key='move'))
        c('stock.transfer',sku='x',source='a',target='b',quantity=2,key='move');assert c('stock.get',sku='x',warehouse='a')['on_hand']==8
        raises(lambda:c('stock.count',sku='x',warehouse='a',expected_on_hand=8,new_on_hand=7,key='count'))
        first=c('stock.count',sku='x',warehouse='a',expected_on_hand=8,new_on_hand=10,key='count');assert first['on_hand']==10
        raises(lambda:c('stock.count',sku='x',warehouse='a',expected_on_hand=8,new_on_hand=11,key='stale'));assert c('stock.count',sku='x',warehouse='a',expected_on_hand=8,new_on_hand=10,key='count')==first
    elif group=='pagination_or_schedule':
        receive(wid='b',q=4);receive(q=3,key='a');order(q=6);o=c('order.confirm',id='o');assert matches(o['allocations'],[line(3),line(3,wid='b')])
        assert c('reorder')==['x','y'];c('order.cancel',id='o');assert c('reorder')==['y']
        c('product.put',sku='x',name='Renamed');assert c('stock.get',sku='x',warehouse='b')['on_hand']==4
    elif group=='history_or_artifacts':
        receive();order(q=4);c('order.confirm',id='o');c('order.ship',id='o',lines=[line(2)],key='s');c('order.cancel',id='o');c('order.return',id='o',lines=[line(1)],key='back');c('stock.transfer',sku='x',source='a',target='b',quantity=2,key='t');c('stock.count',sku='x',warehouse='b',expected_on_hand=2,new_on_hand=2,key='count')
        moves=c('movement.list',sku='x');assert [m['kind']for m in moves]==['receive','ship','return','transfer','transfer','count'];assert [m['delta']for m in moves]==[10,-2,1,-2,2,0];assert [m['sequence']for m in moves]==sorted({m['sequence']for m in moves})
    elif group=='recovery_or_returns':
        receive();order(q=6);c('order.confirm',id='o');c('order.ship',id='o',lines=[line(2)],key='s');c('order.cancel',id='o');assert c('stock.get',sku='x',warehouse='a')['reserved']==0
        c('order.return',id='o',lines=[line(1),line(1)],key='back');before=c('movement.list');raises(lambda:c('order.return',id='o',lines=[line(1)],key='more'));assert c('movement.list')==before
        assert c('stock.get',sku='x',warehouse='a')['on_hand']==10;c('order.cancel',id='o');assert c('order.get',id='o')['status']=='cancelled'
    elif group=='validation':
        rows=[{'sku':'x','quantity':2},{'sku':'x','quantity':3}];before=copy.deepcopy(rows);assert matches(c('order.create',id='o',lines=rows)['lines'],[{'sku':'x','quantity':5}])and rows==before
        for op,kw in [('product.put',{'sku':True,'name':'x'}),('stock.receive',{'sku':'x','warehouse':'a','quantity':True,'key':'bad'}),('order.create',{'id':'bad','lines':[]}),('order.create',{'id':'bad','lines':[{'sku':'missing','quantity':1}]}),('stock.count',{'sku':'x','warehouse':'a','expected_on_hand':False,'new_on_hand':1,'key':'bad'})]:raises(lambda op=op,kw=kw:c(op,**kw))
        assert c('movement.list')==[]
        for i in range(5):
            sku='property'+str(i);total=rng.randrange(3,20);q=rng.randrange(1,total+1);back=rng.randrange(q+1)
            c('product.put',sku=sku,name='Generated');receive(sku=sku,q=total,key='prop-r'+str(i));order(oid='prop-o'+str(i),q=q,sku=sku);c('order.confirm',id='prop-o'+str(i));c('order.ship',id='prop-o'+str(i),lines=[line(q,sku)],key='prop-s'+str(i))
            if back:c('order.return',id='prop-o'+str(i),lines=[line(back,sku)],key='prop-b'+str(i))
            assert matches(c('stock.get',sku=sku,warehouse='a'),{'on_hand':total-q+back,'reserved':0,'available':total-q+back})
    return c
