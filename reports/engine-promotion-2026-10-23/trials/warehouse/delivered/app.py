from goalpilot_runtime import ReplayService, require, fields, text, integer, sequence, idempotent, get_record


def banner(): return 'Local Ops — café'

def positive(x): return integer(x, minimum=1)
def lines(value, field):
    sequence(lambda x: fields(x, {field: text, 'quantity': positive}), nonempty=True)(value)
    totals = {}
    for row in value: totals[row[field]] = totals.get(row[field], 0) + row['quantity']
    return [{field: k, 'quantity': v} for k, v in sorted(totals.items())]

def counts(rows): return {r['lot']: r['quantity'] for r in rows}
def rows(values): return [{'lot': k, 'quantity': v} for k, v in sorted(values.items()) if v]


class Service(ReplayService):
    def initial(self): return {'products': {}, 'lots': {}, 'orders': {}, 'keys': {}}

    def handle(self, s, op, d):
        if op == 'product.put':
            fields(d, {'id': text, 'name': text})
            s['products'][d['id']] = dict(d)
            return s['products'][d['id']]
        if op == 'lot.receive':
            fields(d, {'id': text, 'product': text, 'quantity': positive, 'expires': integer, 'key': text})
            def receive():
                require(d['id'] not in s['lots'], 'Lot exists')
                get_record(s['products'], d['product'])
                lot = dict(id=d['id'], product=d['product'], on_hand=d['quantity'], reserved=0, expires=d['expires'])
                s['lots'][d['id']] = lot
                return lot
            return idempotent(s, d['key'], op, d, receive)
        if op == 'lot.import':
            fields(d, {'lots': sequence(lambda x: fields(x, {'id': text, 'product': text, 'quantity': positive, 'expires': integer, 'key': text}))})
            for lot in d['lots']: self.handle(s, 'lot.receive', lot)
            return {'imported': len(d['lots'])}
        if op == 'order.create':
            fields(d, {'id': text, 'lines': lambda x: lines(x, 'product')})
            normalized = lines(d['lines'], 'product')
            require(d['id'] not in s['orders'], 'Order exists')
            for line in normalized: get_record(s['products'], line['product'])
            order = dict(id=d['id'], status='draft', lines=normalized, allocations=[], shipped=[], returned=[])
            s['orders'][d['id']] = order
            return order
        if op == 'order.allocate':
            fields(d, {'id': text, 'now': integer})
            order = get_record(s['orders'], d['id'])
            if order['status'] == 'confirmed': return order
            require(order['status'] == 'draft', 'Order is not draft')
            allocations = {}
            for line in order['lines']:
                remaining = line['quantity']
                for lot in sorted(s['lots'].values(), key=lambda l: (l['expires'], l['id'])):
                    if lot['product'] != line['product'] or lot['expires'] <= d['now']: continue
                    take = min(remaining, lot['on_hand'] - lot['reserved'])
                    if take: allocations[lot['id']] = take
                    remaining -= take
                require(remaining == 0, 'Insufficient stock')
            for lot, qty in allocations.items(): s['lots'][lot]['reserved'] += qty
            order.update(status='confirmed', allocations=rows(allocations))
            return order
        if op in ('order.ship', 'order.return'):
            fields(d, {'id': text, 'lines': lambda x: lines(x, 'lot'), 'key': text})
            normalized = dict(d, lines=lines(d['lines'], 'lot'))
            def move():
                order = get_record(s['orders'], d['id'])
                shipping = op == 'order.ship'
                if shipping: require(order['status'] in ('confirmed', 'partial'), 'Order cannot ship')
                ceiling = counts(order['allocations'] if shipping else order['shipped'])
                accumulated = counts(order['shipped'] if shipping else order['returned'])
                for line in normalized['lines']:
                    lot, qty = line['lot'], line['quantity']
                    require(qty <= ceiling.get(lot, 0) - accumulated.get(lot, 0), 'Quantity exceeds remaining')
                    record = get_record(s['lots'], lot)
                    record['on_hand'] += -qty if shipping else qty
                    if shipping: record['reserved'] -= qty
                    accumulated[lot] = accumulated.get(lot, 0) + qty
                order['shipped' if shipping else 'returned'] = rows(accumulated)
                if shipping: order['status'] = 'shipped' if accumulated == ceiling else 'partial'
                return order
            return idempotent(s, d['key'], op, normalized, move)
        if op == 'order.cancel':
            fields(d, {'id': text})
            order = get_record(s['orders'], d['id'])
            if order['status'] == 'cancelled': return order
            require(order['status'] in ('draft', 'confirmed', 'partial'), 'Order cannot cancel')
            shipped = counts(order['shipped'])
            for line in order['allocations']:
                s['lots'][line['lot']]['reserved'] -= line['quantity'] - shipped.get(line['lot'], 0)
            order['status'] = 'cancelled'
            return order
        if op == 'order.get':
            fields(d, {'id': text})
            return get_record(s['orders'], d['id'])
        if op == 'lot.list':
            fields(d, {}, {'product': text, 'now': integer})
            if 'product' in d: get_record(s['products'], d['product'])
            return [dict(l, available=l['on_hand'] - l['reserved']) for l in sorted(s['lots'].values(), key=lambda l: (l['expires'], l['id'])) if ('product' not in d or l['product'] == d['product']) and ('now' not in d or l['expires'] > d['now'])]
        if op == 'stock.report':
            fields(d, {'product': text, 'now': integer})
            get_record(s['products'], d['product'])
            lots = [l for l in s['lots'].values() if l['product'] == d['product']]
            return dict(on_hand=sum(l['on_hand'] for l in lots), reserved=sum(l['reserved'] for l in lots), available=sum(l['on_hand']-l['reserved'] for l in lots if l['expires'] > d['now']), expired=sum(l['on_hand'] for l in lots if l['expires'] <= d['now']))
        raise ValueError('Unknown operation')


if __name__ == '__main__': Service.main()
