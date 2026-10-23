"""Twenty distinct local service missions; fixture/judge unavailable to builders.

These are synthetic stdlib stateful service projects, not arbitrary-repository claims.
"""
from pathlib import Path
import json,subprocess,sys,tempfile,os
COMMON='''# Complete the local operations application
Implement the whole public contract below autonomously, with Python standard library only.
Preserve banner() == 'Local Ops — café' and the exact original USER_NOTES.txt. Expose
app.Service(path).call(operation, data) -> JSON value. Persist all application data as JSON,
survive fresh Service instances AND processes. Accepted mutations are atomic; any rejected
request leaves existing data-file bytes unchanged. Concurrent processes must not lose updates
or violate capacities/revisions. Return detached snapshots and don't mutate caller input.
Unknown operations/missing records/invalid fields raise ValueError. IDs/text nonempty strings;
strict integer fields reject booleans, floats and strings. Lists of IDs normalized sorted unique
unless an execution/insertion order is explicitly required. No external network or credentials.

Implement BOTH real public transports using the same business logic:
python app.py --file PATH jsonl consumes one {operation:STRING,data:OBJECT} per line and emits
one {ok:true,result:VALUE} or {ok:false,error:NONEMPTY_TEXT}. Bad JSON/packets/operations must not
prevent the next valid line. python app.py --file PATH serve --port 0 binds localhost, announces
{"port":PORT} as its first stdout line. GET /health ->200 {ok:true}; POST /api uses the same
packet/response envelope with HTTP200 success/400 rejected; unknown path ->404 JSON error.
Unicode supported everywhere. Include meaningful domain, rejection, persistence and real
JSONL/HTTP regression tests and brief usage documentation.

backup {} returns the complete application state as a detached JSON object. restore {state:OBJECT}
validates ALL domain/referential/capacity/history invariants before replacing it atomically.
Invalid/malformed/inconsistent backups reject without losing any current data. Restore a
valid prior snapshot and continue normal operation. Never erase unrelated customer data.
The specified business workflows must work TOGETHER; a passing legacy banner test is insufficient.
'''
CASES={}
def add(name,goal,spec,judge):
 assert name not in CASES
 CASES[name]={'goal':goal,'spec':spec,'judge':judge}

add('rental','Termine la gestion de location de matériel de bout en bout : disponibilités, réservations, retraits, retours et frais, sans doubles réservations ni perte de données.',
'''## Assets, bookings and returns
asset.put {id,quantity:NONNEGATIVE_INT,rate:NONNEGATIVE_CENTS} creates/replaces stock metadata;
reject lowering quantity below concurrent confirmed/active bookings' peak capacity. asset.list
returns sorted assets. Booking intervals are half-open [start,end), strict nonnegative integer
start and end>start. booking.create {id,asset,quantity:POSITIVE_INT,start,end,key} creates a
confirmed booking when concurrent reserved quantity at EVERY instant fits the asset quantity.
Unique booking ID. Idempotency key global: same normalized create returns ORIGINAL snapshot;
changed payload rejects; rejected requests do not consume their key. Return booking
{id,asset,quantity,start,end,status:'confirmed',revision:1,fee:0}. Rate is snapshotted at booking.
booking.pickup {id,expected_revision,now} exact revision; confirmed only; start<=now<end.
Sets active, revision+1. booking.return {id,expected_revision,now,damaged:NONNEGATIVE_INT}
active only, exact revision, now>=start, damaged<=quantity. Sets returned, revision+1,
fee=quantity*(end-start)*snapshotted_rate + max(0,now-end)*quantity*snapshotted_rate + damaged*100.
Return exactly once, reject second return. booking.cancel {id,expected_revision} confirmed only,
sets cancelled, revision+1, frees capacity. Returned/cancelled bookings don't reserve capacity.
booking.get {id} returns snapshot. available {asset,start,end} returns {quantity:MINIMUM_FREE}
over the full interval, counting only confirmed/active bookings; adjacent intervals don't conflict.
booking.list {asset optional,status optional} returns sorted bookings with conjunctive filters.
booking.import {bookings:[create-payloads]} all-or-none, including overlap and key conflicts
within batch. Return {imported:N}. Replays with existing keys may appear; do not double reserve.
Restore validates references, interval/quantity types, statuses/revisions, global keys, fee and
capacity invariants; changing live rates never changes existing booking fee calculation.
''',r'''
c('asset.put',id='drill',quantity=3,rate=10)
a=c('booking.create',id='a',asset='drill',quantity=2,start=0,end=10,key='ka')
b=c('booking.create',id='b',asset='drill',quantity=1,start=5,end=15,key='kb')
assert c('available',asset='drill',start=0,end=15)=={'quantity':0}
before=db.read_bytes();reject('booking.create',id='bad',asset='drill',quantity=1,start=9,end=11,key='kbad');assert db.read_bytes()==before
assert c('booking.create',id='a',asset='drill',quantity=2,start=0,end=10,key='ka')==a
check('capacity_and_idempotency')
c('booking.create',id='adj',asset='drill',quantity=2,start=10,end=20,key='kc')
reject('asset.put',id='drill',quantity=2,rate=100)
c('asset.put',id='drill',quantity=3,rate=100)
c('booking.pickup',id='a',expected_revision=1,now=1)
r=c('booking.return',id='a',expected_revision=2,now=12,damaged=1)
assert r['fee']==340 and r['status']=='returned'
reject('booking.return',id='a',expected_revision=3,now=13,damaged=0)
check('snapshot_fee_and_return')
reject('booking.cancel',id='b',expected_revision=2)
c('booking.cancel',id='b',expected_revision=1)
assert c('available',asset='drill',start=0,end=10)=={'quantity':3}
assert [x['id']for x in c('booking.list',status='cancelled')]==['b']
check('cancel_revision_filters')
before=db.read_bytes();reject('booking.import',bookings=[{'id':'x','asset':'drill','quantity':1,'start':30,'end':40,'key':'kx'},{'id':'y','asset':'drill','quantity':4,'start':30,'end':40,'key':'ky'}]);assert db.read_bytes()==before
reject('booking.create',id='z',asset='drill',quantity=True,start=30,end=40,key='kz')
check('atomic_batch_and_types')
''')

add('invoices','Achève cette facturation locale : lignes exactes en centimes, paiements, avoirs et rapprochement, avec les parcours complets et la reprise après redémarrage.',
'''## Invoice lifecycle and exact money
customer.put {id,name} upserts customer; customer.list {} sorted. invoice.create
{id,customer,lines:[{description,quantity:POSITIVE_INT,unit_cents:NONNEGATIVE_INT}],tax_bps:INT0..10000}
creates unique draft, returns {id,customer,status:'draft',lines,subtotal,tax,total,paid:0,credited:0,
balance:total,revision:1}. Lines nonempty, preserve order; subtotal=sum(quantity*unit_cents),
tax=(subtotal*tax_bps+5000)//10000 (round half up), total=subtotal+tax. Customer must exist.
invoice.issue {id,expected_revision} draft only, exact revision, status issued, revision+1.
invoice.pay {id,amount:POSITIVE_CENTS,key} issued/partial only, amount<=balance. Global keys:
same operation and payload returns original snapshot, changed request rejects without effects.
Increase paid; balance=total-paid-credited, status paid if zero else partial, revision+1.
invoice.credit {id,amount:POSITIVE_CENTS,key} issued/partial/paid allowed, amount<=total-credited;
credit cannot make balance negative (thus amount<=current balance); update credited, balance,
status credited if balance zero and paid zero, paid if balance zero otherwise partial; revision+1.
No payment/credit on draft/void/credited. invoice.void {id,expected_revision} draft/issued only,
no paid or credited money, exact revision; sets void, balance0, revision+1. No further money ops.
invoice.get {id}; invoice.list {customer optional,status optional} sorted IDs.
payment.import {payments:[{id,amount,key}]} atomically apply all payment operations, including
idempotency and cumulative limits; return {imported:N}. statement {customer} returns
{invoiced:SUM_TOTAL_EXCLUDING_VOID,paid:SUM_PAID,credited:SUM_CREDITED,due:SUM_BALANCE}.
Restore validates customers, line totals/tax rounding, nonnegative money, statuses/revisions,
referential integrity and key snapshots. No floats for arithmetic. Failed batch never reserves keys.
''',r'''
c('customer.put',id='c',name='Zoé');r=c('invoice.create',id='i',customer='c',lines=[{'description':'A','quantity':3,'unit_cents':15}],tax_bps=1000)
assert (r['subtotal'],r['tax'],r['total'],r['balance'])==(45,5,50,50)
reject('invoice.pay',id='i',amount=1,key='early')
c('invoice.issue',id='i',expected_revision=1);r=c('invoice.pay',id='i',amount=20,key='p1')
assert r['status']=='partial' and r['paid']==20 and r['balance']==30
assert c('invoice.pay',id='i',amount=20,key='p1')==r
check('rounding_issue_payment')
before=db.read_bytes();reject('invoice.pay',id='i',amount=21,key='p1');reject('invoice.credit',id='i',amount=31,key='c1');assert db.read_bytes()==before
r=c('invoice.credit',id='i',amount=10,key='c1');assert r['balance']==20
c('invoice.pay',id='i',amount=20,key='p2');assert c('invoice.get',id='i')['status']=='paid'
assert c('statement',customer='c')=={'invoiced':50,'paid':40,'credited':10,'due':0}
check('credit_idempotency_statement')
c('invoice.create',id='v',customer='c',lines=[{'description':'V','quantity':1,'unit_cents':100}],tax_bps=0)
c('invoice.void',id='v',expected_revision=1);reject('invoice.issue',id='v',expected_revision=2)
assert c('statement',customer='c')['invoiced']==50
check('void_lifecycle')
c('invoice.create',id='b',customer='c',lines=[{'description':'B','quantity':1,'unit_cents':100}],tax_bps=0);c('invoice.issue',id='b',expected_revision=1)
before=db.read_bytes();reject('payment.import',payments=[{'id':'b','amount':50,'key':'batch1'},{'id':'b','amount':60,'key':'batch2'}]);assert db.read_bytes()==before
reject('invoice.pay',id='b',amount=True,key='bool');assert c('invoice.get',id='b')['paid']==0
check('batch_and_types')
''')

add('learning','Termine cette plateforme de cours : prérequis, inscriptions, listes d’attente, validation et remboursements. Chaque parcours doit fonctionner de bout en bout.',
'''## Learning and enrollment
student.put {id,name} upserts student. course.put {id,prerequisites:[IDS],capacity:NONNEGATIVE_INT,
price:NONNEGATIVE_CENTS} upserts course; prerequisite courses must exist, no self/cyclic graph.
Reject reducing capacity below current enrolled count. Enrollment snapshots price at request.
enroll {student,course,key} global idempotency same normalized request returns original snapshot;
changed payload rejects. Student exists, all prerequisites completed; cannot enroll twice in same
course even with another key (cancelled enrollment permits a new request). Enrolled if a seat
available else waiting. Return {id:OPAQUE,student,course,status:'enrolled'/'waiting',price,score:null}.
Waitlist order is successful request insertion order, independent of student ID. enrollment.get
{id}; enrollment.list {course optional,student optional} list in insertion order.
complete {id,score:INT0..100} enrolled only; sets completed and records score; score>=60 marks
student course completed for prerequisites. A failed completed enrollment still frees seat but
is not a prerequisite pass. No completion from waiting/cancelled/completed. Completion frees
capacity and promotes the earliest valid waiting enrollment to enrolled automatically.
cancel {id} waiting/enrolled only, idempotent if already cancelled. Sets cancelled, refund equals
snapshotted price for enrolled, zero for waiting; return {id,status:'cancelled',refund:...}.
Frees seat and promotes earliest waiting enrollment. Promotion snapshots no new price.
course.report {id} returns {enrolled:COUNT,waiting:COUNT,completed:COUNT,cancelled:COUNT,
revenue:SUM_PRICE_OF_ENROLLED_AND_COMPLETED,waitlist:[STUDENT_IDS_IN_ORDER]}.
enroll.import {requests:[{student,course,key}]} all-or-none across prerequisites, duplicate
students and capacity transitions; return {imported:N}. Unknown course/student or invalid key
rolls back all requests. Restore validates DAG, enrollment references/statuses/prices/scores,
capacity, waitlist order, completed prerequisite history and idempotency snapshots.
''',r'''
for x in ['a','b','c']:c('student.put',id=x,name=x)
c('course.put',id='base',prerequisites=[],capacity=1,price=100)
c('course.put',id='advanced',prerequisites=['base'],capacity=1,price=200)
reject('enroll',student='a',course='advanced',key='early')
a=c('enroll',student='a',course='base',key='a');b=c('enroll',student='b',course='base',key='b');z=c('enroll',student='c',course='base',key='c')
assert a['status']=='enrolled' and b['status']==z['status']=='waiting'
assert c('enroll',student='a',course='base',key='a')==a
check('prerequisites_capacity_idempotency')
c('course.put',id='base',prerequisites=[],capacity=1,price=500)
c('complete',id=a['id'],score=80)
assert c('enrollment.get',id=b['id'])['status']=='enrolled' and c('enrollment.get',id=b['id'])['price']==100
assert c('enroll',student='a',course='advanced',key='aa')['status']=='enrolled'
assert c('course.report',id='base')['waitlist']==['c']
check('complete_promotion_snapshot')
r=c('cancel',id=b['id']);assert r['refund']==100 and c('cancel',id=b['id'])==r
assert c('enrollment.get',id=z['id'])['status']=='enrolled'
assert c('course.report',id='base')=={'enrolled':1,'waiting':0,'completed':1,'cancelled':1,'revenue':200,'waitlist':[]}
check('refund_waitlist_report')
before=db.read_bytes();reject('enroll.import',requests=[{'student':'b','course':'base','key':'batch'},{'student':'missing','course':'base','key':'bad'}]);assert db.read_bytes()==before
reject('complete',id=z['id'],score=True);reject('course.put',id='base',prerequisites=['advanced'],capacity=1,price=0)
check('atomic_import_types_cycles')
''')

add('tickets','Finalise la billetterie locale : sièges, réservations temporaires, expiration, achat, remboursement et contrôle d’entrée. Aucun siège vendu deux fois.',
'''## Events, holds and admission
event.create {id,seats:[NONEMPTY_STRINGS],price:NONNEGATIVE_CENTS} creates event with unique seats,
normalized sorted; duplicate event rejects. event.get {id,now:NONNEGATIVE_INT} returns
{id,seats,price,available:[SEAT_IDS_SORTED]}. Holds cease reserving at now>=expires; purchases
reserve until refunded. hold.create {id,event,seats:[IDS],now,ttl:POSITIVE_INT} nonempty selection,
unique hold ID, all seats known/free; all-or-none. Return {id,event,seats,expires:now+ttl,
status:'held',price:NUMBER_OF_SEATS*event_price}. hold.cancel {id} held only, idempotent after
cancelled; mark cancelled. purchase {hold,now,key} valid held and now<expires only, global key
idempotent same request returns original result even after later changes/expiry. Key conflict
rejects. Return order {id:OPAQUE,event,seats,total,status:'paid',used:[]}. Mark hold purchased.
order.get {id}. order.refund {id} paid only, rejects if ANY seat used, marks refunded and releases
seats. Replayed refund idempotent; total unchanged. checkin {order,seat} paid order and contained
seat not previously used; add sorted used, return {order,seat,admitted:true}. Duplicate admission
rejects with no effects. Refunded orders cannot check in. Seat resale after refund is allowed.
hold.import {holds:[hold-create-payloads]} all-or-none including conflicts between rows and
expiry evaluated using each row's own now. Return {imported:N}. sales.report {event} returns
{paid:SUM_TOTAL_PAID,refunded:SUM_TOTAL_REFUNDED,admitted:SUM_USED_SEATS_PAID}.
Strict time/TTL/int/ID validation; bool not accepted. Concurrent holds for same seat at same
logical time have exactly one winner. Restore validates all references, seats/amounts/statuses,
no duplicate active sales, used-seat membership and receipts; expiry remains logical-time driven.
''',r'''
c('event.create',id='e',seats=['B','A','C'],price=150)
h=c('hold.create',id='h',event='e',seats=['B','A'],now=0,ttl=10);assert h['seats']==['A','B'] and h['price']==300
before=db.read_bytes();reject('hold.create',id='x',event='e',seats=['B','C'],now=9,ttl=10);assert db.read_bytes()==before
assert c('event.get',id='e',now=10)['available']==['A','B','C']
reject('purchase',hold='h',now=10,key='expired')
check('seat_atomicity_expiry')
c('hold.create',id='h2',event='e',seats=['A','B'],now=10,ttl=10)
o=c('purchase',hold='h2',now=11,key='buy');assert o['total']==300 and o['status']=='paid'
assert c('purchase',hold='h2',now=11,key='buy')==o
reject('purchase',hold='h2',now=12,key='buy')
assert c('event.get',id='e',now=100)['available']==['C']
check('purchase_idempotency_restart')
r=c('checkin',order=o['id'],seat='A');assert r['admitted'] is True
reject('checkin',order=o['id'],seat='A');reject('order.refund',id=o['id'])
assert c('sales.report',event='e')=={'paid':300,'refunded':0,'admitted':1}
check('checkin_no_refund_after_use')
c('hold.create',id='h3',event='e',seats=['C'],now=100,ttl=10);other=c('purchase',hold='h3',now=101,key='buy3')
c('order.refund',id=other['id']);c('order.refund',id=other['id']);assert c('event.get',id='e',now=110)['available']==['C']
before=db.read_bytes();reject('hold.import',holds=[{'id':'b1','event':'e','seats':['C'],'now':200,'ttl':10},{'id':'b2','event':'e','seats':['A'],'now':200,'ttl':10}]);assert db.read_bytes()==before
reject('hold.create',id='bool',event='e',seats=['C'],now=200,ttl=True)
check('refund_batch_types')
''')

add('procurement','Achève cet outil d’achats : budgets, demandes, approbations séparées, engagements et remboursements. Préserve les comptes et tous les contrôles métier.',
'''## Department budgets and purchase requests
department.put {id,budget:NONNEGATIVE_CENTS} creates/replaces budget; cannot set below committed
plus spent amount. member.put {id,department,role:'requester'/'approver'} upserts member, known
department; changing role/department cannot invalidate pending request creator/approvals.
request.create {id,creator,amount:POSITIVE_CENTS,approvals:POSITIVE_INT} unique request, creator
exists (either role). Return {id,creator,department,amount,approvals,approved:[],status:'pending',
revision:1,refunded:0}. Snapshot creator department; creating doesn't reserve budget.
request.approve {id,actor,expected_revision} pending only, exact revision. Actor approver in same
department, different from creator, not already approved. Add actor sorted and revision+1.
When count reaches required approvals, atomically reserve amount from department available
budget and set status approved. If insufficient funds reject the entire approval and revision.
request.reject {id,actor,expected_revision} pending/approved, same authorized different actor,
exact revision; status rejected, revision+1, release commitment if approved.
request.spend {id,key} approved only; global key same request returns original snapshot, conflict
rejects; convert committed to spent, status spent, revision+1. request.refund {id,amount,key}
spent only, amount<=amount-refunded; reduce department spent, increase refunded, revision+1.
A fully refunded request remains spent. Keys global across spend/refund; normalized payload
includes operation. Failed operations never consume keys. request.get {id} returns snapshot.
department.report {id} -> {budget,committed,spent,available:budget-committed-spent}.
request.import {requests:[create-payloads]} creates batch all-or-none, rejects unknown creator,
repeated/existing ID, invalid amounts or approvals; return {imported:N}.
Restore validates member/reference/role/status/revision/approval separation, balances, caps and
refund/idempotency history. Concurrent final approvals cannot overcommit a budget.
''',r'''
c('department.put',id='d',budget=1000)
for ident,role in [('req','requester'),('a','approver'),('b','approver')]:c('member.put',id=ident,department='d',role=role)
c('request.create',id='r',creator='req',amount=600,approvals=2)
reject('request.approve',id='r',actor='req',expected_revision=1)
c('request.approve',id='r',actor='a',expected_revision=1);r=c('request.approve',id='r',actor='b',expected_revision=2)
assert r['status']=='approved' and c('department.report',id='d')=={'budget':1000,'committed':600,'spent':0,'available':400}
check('separation_and_commitment')
c('request.create',id='x',creator='req',amount=500,approvals=1)
before=db.read_bytes();reject('request.approve',id='x',actor='a',expected_revision=1);assert db.read_bytes()==before
r=c('request.spend',id='r',key='spend');assert r['status']=='spent' and c('request.spend',id='r',key='spend')==r
assert c('department.report',id='d')['spent']==600
check('budget_atomicity_spend_replay')
r=c('request.refund',id='r',amount=200,key='refund');assert r['refunded']==200
assert c('request.refund',id='r',amount=200,key='refund')==r
reject('request.refund',id='r',amount=401,key='too-much')
c('request.approve',id='x',actor='a',expected_revision=1)
c('request.reject',id='x',actor='b',expected_revision=2)
assert c('department.report',id='d')=={'budget':1000,'committed':0,'spent':400,'available':600}
check('refund_and_release')
before=db.read_bytes();reject('request.import',requests=[{'id':'q','creator':'req','amount':1,'approvals':1},{'id':'bad','creator':'none','amount':2,'approvals':1}]);assert db.read_bytes()==before
reject('department.put',id='d',budget=399);reject('request.create',id='bool',creator='req',amount=True,approvals=1)
check('batch_strict_types_and_budget')
''')

add('accounting','Finalise le grand livre comptable local : écritures équilibrées, périodes clôturées, annulations et balance, avec des montants exacts et une piste d’audit durable.',
'''## Double-entry accounting
account.create {id,name,kind:'asset'/'liability'/'income'/'expense'} unique account, opening zero.
period.create {id,start:NONNEGATIVE_INT,end:INT>start} half-open dated period, no overlap with
existing periods. Return {id,start,end,status:'open',revision:1}. journal.post {id,date:INT,
lines:[{account,debit:NONNEGATIVE_CENTS,credit:NONNEGATIVE_CENTS}],key} unique entry, at least two
lines; each line exactly one positive side (not both or neither), all accounts known, equal
positive debit/credit totals. Date belongs to exactly one OPEN period. Preserve line order and
aggregate account balances across lines. Global idempotency key includes operation/payload;
replay same returns ORIGINAL entry, conflicts reject, failure doesn't consume key. Return
{id,date,period,lines,status:'posted',reversal:null}. journal.reverse {id,reversal_id,date,key}
creates a new balanced entry with sides swapped, current date in open period, unique new ID,
marks original status reversed and reversal ID. Cannot reverse twice, but identical key replay
returns original reversal snapshot. Cannot reverse a reversal entry. Entry history immutable.
period.close {id,expected_revision} open/exact revision, mark closed/revision+1; subsequent post
or reversal dated within it rejects. period.reopen {id,expected_revision} closed/exact revision,
mark open/revision+1. journal.get {id}; journal.list {period optional,account optional} entries
sorted by (date,id), including originals and reversals. account.balance {id} -> {debit,credit,
net:debit-credit}; trial_balance {} -> sorted [{account,debit,credit,net}] including zero accounts.
journal.import {entries:[post-payloads]} all-or-none, enforcing cumulative IDs/keys/balance/periods,
return {imported:N}. A rejected batch must not alter account balances or reserve IDs/keys.
Restore validates all accounts/periods, no overlapping dates, balanced immutable entries,
reversal references/sides, types and key snapshots. Original reversed entry still counts in
balances; its separate reversal offsets it, never remove history. Concurrent posts don't lose data.
''',r'''
for aid,kind in [('cash','asset'),('sales','income')]:c('account.create',id=aid,name=aid,kind=kind)
c('period.create',id='p',start=0,end=100)
lines=[{'account':'cash','debit':123,'credit':0},{'account':'sales','debit':0,'credit':123}]
e=c('journal.post',id='e',date=1,lines=lines,key='k');assert e['status']=='posted'
assert c('journal.post',id='e',date=1,lines=lines,key='k')==e
assert c('account.balance',id='cash')=={'debit':123,'credit':0,'net':123}
check('balanced_post_exact_money')
before=db.read_bytes();reject('journal.post',id='bad',date=2,lines=[{'account':'cash','debit':1,'credit':0},{'account':'sales','debit':0,'credit':2}],key='bad');assert db.read_bytes()==before
c('period.close',id='p',expected_revision=1);reject('journal.post',id='late',date=3,lines=lines,key='late')
reject('period.reopen',id='p',expected_revision=1);c('period.reopen',id='p',expected_revision=2)
check('balance_atomicity_closed_periods')
r=c('journal.reverse',id='e',reversal_id='rev',date=4,key='reverse');assert c('journal.reverse',id='e',reversal_id='rev',date=4,key='reverse')==r
assert c('journal.get',id='e')['reversal']=='rev'
assert c('account.balance',id='cash')['net']==0
reject('journal.reverse',id='e',reversal_id='twice',date=5,key='twice')
assert [x['id']for x in c('journal.list',account='cash')]==['e','rev']
check('reversal_history_and_replay')
before=db.read_bytes();reject('journal.import',entries=[{'id':'x','date':6,'lines':lines,'key':'batch'},{'id':'y','date':100,'lines':lines,'key':'badbatch'}]);assert db.read_bytes()==before
reject('period.create',id='overlap',start=99,end=110)
reject('journal.post',id='bool',date=True,lines=lines,key='bool')
assert all(x['net']==0 for x in c('trial_balance'))
check('batch_types_trial_balance')
''')

add('clinic','Termine la prise de rendez-vous d’un cabinet : disponibilités, consentements, reports, listes d’attente et facturation des absences, sans conflit ni perte d’historique.',
'''## Clinic scheduling without patient data dependencies
practitioner.put {id,skills:[STRINGS]} upserts skills; cannot remove a skill referenced by a
non-cancelled appointment. patient.put {id,consent:BOOLEAN} upserts patient. Revoking consent
is allowed, but new bookings for that patient reject. appointment.create {id,patient,practitioner,
start:NONNEGATIVE_INT,end:INT>start,skill,fee:NONNEGATIVE_CENTS,key} creates unique confirmed
appointment, patient consent true and practitioner skilled. Both practitioner AND patient cannot
have overlapping non-cancelled appointment intervals; half-open adjacency allowed. Return
{id,patient,practitioner,start,end,skill,fee,status:'confirmed',revision:1,charged:0}.
Global create keys are idempotent for identical payload, conflicting request rejects; original
snapshot returned even if appointment changed. appointment.move {id,start,end,expected_revision}
confirmed only, exact revision; all overlap checks ignoring self; one atomic revision increase.
appointment.cancel {id,expected_revision} confirmed only, exact revision; sets cancelled and
revision+1, frees interval. appointment.finish {id,expected_revision,attended:BOOLEAN} confirmed
only, exact revision; status attended or missed; charged fee when attended, fee//2 when missed;
revision+1. Completed appointments retain their occupied history for overlap checks.
appointment.get {id}; appointment.list {patient optional,practitioner optional,status optional}
filtered conjunctively and sorted by (start,id). invoice {patient} -> {charged:SUM_CHARGED,
attended:COUNT,missed:COUNT}. wait.add {id,patient,skill} unique wait ID and no duplicate
(patient,skill), consent required; stores insertion order. wait.list {skill} returns original
request objects in insertion order. wait.remove {id} removes existing request. Requests are
not automatically booked; list permits a human scheduler to choose.
appointment.import {appointments:[create-payloads]} all-or-none including conflicts inside batch,
return {imported:N}. Restore validates all references, skills, consent type, time intervals,
non-cancelled overlap histories, statuses/charges/revisions, idempotency and waitlist uniqueness.
Concurrent moves/creates cannot double-book either party. No actual patient secrets involved.
''',r'''
c('practitioner.put',id='dr',skills=['general']);c('patient.put',id='p',consent=True);c('patient.put',id='q',consent=True)
a=c('appointment.create',id='a',patient='p',practitioner='dr',start=0,end=30,skill='general',fee=101,key='ka')
assert c('appointment.create',id='a',patient='p',practitioner='dr',start=0,end=30,skill='general',fee=101,key='ka')==a
before=db.read_bytes();reject('appointment.create',id='bad',patient='q',practitioner='dr',start=29,end=40,skill='general',fee=100,key='bad');assert db.read_bytes()==before
c('appointment.create',id='b',patient='q',practitioner='dr',start=30,end=60,skill='general',fee=99,key='kb')
check('consent_conflicts_adjacency')
reject('appointment.move',id='a',start=20,end=40,expected_revision=1)
r=c('appointment.move',id='a',start=60,end=90,expected_revision=1);assert r['revision']==2
reject('appointment.cancel',id='a',expected_revision=1)
c('appointment.finish',id='a',expected_revision=2,attended=False)
assert c('invoice',patient='p')=={'charged':50,'attended':0,'missed':1}
check('move_revision_no_show')
c('patient.put',id='p',consent=False);reject('wait.add',id='w0',patient='p',skill='general')
c('wait.add',id='w1',patient='q',skill='general');assert [x['id']for x in c('wait.list',skill='general')]==['w1']
reject('wait.add',id='w2',patient='q',skill='general');c('wait.remove',id='w1')
c('appointment.cancel',id='b',expected_revision=1);assert c('appointment.get',id='b')['status']=='cancelled'
check('consent_waitlist_cancel')
before=db.read_bytes();reject('appointment.import',appointments=[{'id':'x','patient':'q','practitioner':'dr','start':100,'end':130,'skill':'general','fee':100,'key':'x'},{'id':'y','patient':'q','practitioner':'dr','start':120,'end':140,'skill':'general','fee':100,'key':'y'}]);assert db.read_bytes()==before
reject('practitioner.put',id='dr',skills=[]);reject('patient.put',id='bad',consent=1)
check('batch_preservation_and_types')
''')

add('incidents','Achève la gestion d’incidents : responsables, SLA, pauses, escalades, résolution et réouverture. Les délais et l’historique doivent rester fiables après reprise.',
'''## Logical-time incident management
team.put {id,members:[IDS]} upserts nonempty member list; cannot remove current assigned owner
of an unresolved incident. policy.put {id,response:POSITIVE_INT,resolve:POSITIVE_INT} upserts SLA,
resolve>=response. incident.open {id,team,policy,now:NONNEGATIVE_INT,title,key} creates unique
incident, snapshots policy. Return {id,team,title,status:'open',owner:null,revision:1,level:0,
acknowledged:null,resolved:null,paused:false}. Global keys same normalized open return ORIGINAL
snapshot, conflicts reject. Clock starts now; all later incident times must be >= last accepted
incident time. incident.assign {id,owner,expected_revision,now} unresolved, owner team member,
exact revision; owner set and revision+1. incident.ack {id,expected_revision,now} open only,
not yet acknowledged, sets acknowledged now and status acknowledged, revision+1.
incident.pause {id,expected_revision,now} unresolved and not paused; records pause start and
paused true, revision+1. incident.resume {id,expected_revision,now} paused only; subtract elapsed
pause from effective elapsed time, paused false and revision+1. Pauses stop BOTH SLA clocks.
incident.resolve {id,expected_revision,now} unresolved and not paused; status resolved,
resolved timestamp now, revision+1. incident.reopen {id,expected_revision,now} resolved only,
status open, resets ack/resolved/pauses and start time to now, retains owner, level0, revision+1.
incident.inspect {id,now} readonly, now>=last accepted incident time; returns public incident
plus elapsed (now-start minus completed/current pauses, frozen at resolved timestamp when
resolved), response_breached (unacknowledged AND elapsed>=snapshot.response AND unresolved),
resolve_breached (unresolved AND elapsed>=snapshot.resolve). Inspection does not advance time.
escalate {id,now,expected_revision} unresolved and currently response or resolve breached;
level+1 and revision+1, one escalation per effective elapsed value (same time rejects).
incident.list {team optional,status optional} sorted IDs. incident.import {incidents:[open-payloads]}
all-or-none, return {imported:N}. Restore validates reference/owner/status/revision/time/pauses/
policy snapshots and escalation history. No wall-clock or external service needed.
''',r'''
c('team.put',id='t',members=['zoé','a']);c('policy.put',id='p',response=10,resolve=30)
a=c('incident.open',id='i',team='t',policy='p',now=0,title='Down',key='k');assert a['status']=='open'
assert c('incident.open',id='i',team='t',policy='p',now=0,title='Down',key='k')==a
assert c('incident.inspect',id='i',now=10)['response_breached'] is True
c('incident.assign',id='i',owner='zoé',expected_revision=1,now=2)
c('incident.pause',id='i',expected_revision=2,now=5)
assert c('incident.inspect',id='i',now=100)['elapsed']==5
check('policy_snapshot_paused_clock')
c('incident.resume',id='i',expected_revision=3,now=105)
c('policy.put',id='p',response=1000,resolve=2000)
r=c('escalate',id='i',expected_revision=4,now=110);assert r['level']==1
reject('escalate',id='i',expected_revision=5,now=110)
c('incident.ack',id='i',expected_revision=5,now=111)
assert not c('incident.inspect',id='i',now=112)['response_breached']
assert c('incident.inspect',id='i',now=130)['resolve_breached']
check('escalation_ack_snapshot')
c('incident.resolve',id='i',expected_revision=6,now=131)
r=c('incident.inspect',id='i',now=999);assert r['elapsed']==31 and not r['resolve_breached']
c('incident.reopen',id='i',expected_revision=7,now=1000)
r=c('incident.inspect',id='i',now=1009);assert r['elapsed']==9 and r['level']==0 and r['owner']=='zoé'
reject('team.put',id='t',members=['a'])
check('resolution_reopen_owner')
before=db.read_bytes();reject('incident.import',incidents=[{'id':'x','team':'t','policy':'p','now':0,'title':'X','key':'x'},{'id':'y','team':'none','policy':'p','now':0,'title':'Y','key':'y'}]);assert db.read_bytes()==before
reject('incident.pause',id='i',expected_revision=8,now=999)
reject('policy.put',id='bad',response=True,resolve=3)
check('batch_time_and_types')
''')

add('flags','Finalise la gestion de fonctionnalités : ciblage, déploiement progressif déterministe, publication, retour arrière et audit. Vérifie les règles et l’isolation des environnements.',
'''## Deterministic local feature flag service
environment.create {id} unique environment. segment.put {environment,id,members:[USER_IDS]}
upserts sorted unique membership. flag.create {environment,id,default:BOOLEAN} unique flag in
environment; return {id,environment,revision:1,published:0,enabled:false,default,rules:[]}.
flag.update {environment,id,expected_revision,enabled:BOOLEAN,rules:[RULES]} exact draft revision;
validate every rule before effects. Rules in order, each {segment:ID_OR_NULL,percent:INT0..100,
value:BOOLEAN}; segment must exist when nonnull, null means all users. revision+1, only draft
changes; live evaluations unaffected until publish. flag.publish {environment,id,expected_revision}
exact revision, stores immutable current snapshot as published revision, return flag. Republishing
same revision idempotent, no revision bump. flag.evaluate {environment,id,user} uses published
snapshot if any, otherwise default create value. Disabled live flag always yields its default.
For each live rule in order, only matching segment/all-users eligible. Compute bucket =
int.from_bytes(SHA256(UTF8(environment+'|'+flag_id+'|'+user)).digest()[:8],'big') %100.
First eligible rule with bucket<percent wins; otherwise default. Return {value:BOOLEAN,
revision:LIVE_REVISION_OR_0,bucket:INT}. Membership is evaluated from CURRENT segment state;
rule definitions/value/enable/default from immutable published snapshot.
flag.rollback {environment,id,revision:PREVIOUSLY_PUBLISHED_REVISION,expected_revision:CURRENT_DRAFT}
loads old published snapshot into a NEW draft revision current+1 and immediately publishes it.
Unknown historic revision/stale CAS rejects. flag.get {environment,id} current draft; flag.list
{environment} sorted IDs. audit.list {environment} returns append-only ordered events
{sequence,kind,flag,revision} for flag.created/updated/published/rolled_back; create/update/rollback
one each, successful publish one except idempotent replay. Segment changes produce no flag event.
segment.delete {environment,id} rejects if referenced in ANY current draft or published history.
flag.import {environment,flags:[{id,default}]} create batch all-or-none; return {imported:N}.
Restore validates environment isolation, rule/reference/types, revision history and audit sequence.
''',r'''
import hashlib
c('environment.create',id='prod');c('environment.create',id='dev')
c('segment.put',environment='prod',id='staff',members=['zoé'])
c('flag.create',environment='prod',id='f',default=False)
c('flag.update',environment='prod',id='f',expected_revision=1,enabled=True,rules=[{'segment':'staff','percent':100,'value':True}])
assert c('flag.evaluate',environment='prod',id='f',user='zoé')['value'] is False
c('flag.publish',environment='prod',id='f',expected_revision=2)
r=c('flag.evaluate',environment='prod',id='f',user='zoé');assert r['value'] is True and r['revision']==2
assert r['bucket']==int.from_bytes(hashlib.sha256('prod|f|zoé'.encode()).digest()[:8],'big')%100
check('draft_publish_determinism')
c('flag.update',environment='prod',id='f',expected_revision=2,enabled=False,rules=[])
assert c('flag.evaluate',environment='prod',id='f',user='zoé')['value'] is True
c('segment.put',environment='prod',id='staff',members=[]);assert c('flag.evaluate',environment='prod',id='f',user='zoé')['value'] is False
c('flag.publish',environment='prod',id='f',expected_revision=3);c('flag.publish',environment='prod',id='f',expected_revision=3)
c('segment.put',environment='prod',id='staff',members=['zoé'])
c('flag.rollback',environment='prod',id='f',revision=2,expected_revision=3)
assert c('flag.evaluate',environment='prod',id='f',user='zoé')['value'] is True
check('snapshot_membership_rollback')
events=c('audit.list',environment='prod');assert [e['kind']for e in events]==['flag.created','flag.updated','flag.published','flag.updated','flag.published','flag.rolled_back']
assert [e['sequence']for e in events]==list(range(1,7))
reject('segment.delete',environment='prod',id='staff');reject('flag.get',environment='dev',id='f')
check('audit_and_environment_isolation')
before=db.read_bytes();reject('flag.import',environment='dev',flags=[{'id':'x','default':True},{'id':'y','default':1}]);assert db.read_bytes()==before
reject('flag.update',environment='prod',id='f',expected_revision=3,enabled=True,rules=[])
check('atomic_import_strict_boolean_cas')
''')

add('outbox','Termine cette messagerie locale durable : publication, déduplication, livraison par baux, nouvelles tentatives et file d’échecs. Rien ne doit disparaître au redémarrage.',
'''## Durable queue, leases and dead letters
queue.create {id,max_attempts:POSITIVE_INT,retry_delay:NONNEGATIVE_INT} unique queue. message.publish
{queue,id,payload:JSON_VALUE,key,priority:INT optional0,not_before:NONNEGATIVE_INT optional0}
unique ID per queue. Global key same normalized publish returns original message snapshot,
conflict rejects without effects. Return {id,queue,payload,status:'pending',attempts:0,priority,
not_before,receipt:null,worker:null}. message.get {queue,id} returns detached message.
claim {queue,worker,now:NONNEGATIVE_INT,lease:POSITIVE_INT,limit:INT1..100} first expire all
leased messages with now>=expiry: pending with not_before=now+retry_delay unless attempts
>=max_attempts then dead. Eligible pending not_before<=now, order descending priority then ID.
For each acquired message increment attempts once, status leased, new opaque receipt different
on every claim, worker set and expires=now+lease. Return acquired message snapshots. No model,
network or real scheduler involved. Two concurrent claims cannot lease the same message.
ack {queue,id,receipt,now} only current leased unexpired receipt, sets done and clears lease
fields. Repeated/stale/expired/wrong receipt rejects, never completes message accidentally.
nack {queue,id,receipt,now} valid current unexpired lease only, sets pending with
not_before=now+retry_delay or dead when attempts>=max_attempts; clears lease fields.
redrive {queue,id,now} dead only; pending, attempts0, not_before=now; old receipt stays invalid.
message.cancel {queue,id} pending only, mark cancelled; done/dead/leased reject. queue.stats
{queue,now} performs expiry handling then returns counts {pending,leased,done,dead,cancelled}.
message.list {queue,status optional} sorted IDs. publish.import {messages:[publish-payloads]}
all-or-none, including ID/key conflicts, return {imported:N}. Strict types even priority bool.
Restore validates queues/references/statuses/attempt limits/lease consistency/receipts and key
snapshots, preserves opaque receipt uniqueness across restarts. Failed ack/nack never performs
unrelated mutations, including implicit expiry; stats/claim alone perform expiry changes.
''',r'''
c('queue.create',id='q',max_attempts=2,retry_delay=5)
a=c('message.publish',queue='q',id='a',payload={'café':[1]},key='a',priority=1)
c('message.publish',queue='q',id='b',payload=2,key='b',priority=3)
assert c('message.publish',queue='q',id='a',payload={'café':[1]},key='a',priority=1)==a
rows=c('claim',queue='q',worker='w',now=0,lease=10,limit=1);assert rows[0]['id']=='b' and rows[0]['attempts']==1
old=rows[0]['receipt'];c('nack',queue='q',id='b',receipt=old,now=1)
assert [r['id']for r in c('claim',queue='q',worker='w',now=2,lease=10,limit=2)]==['a']
check('priority_idempotency_delayed_retry')
rows=c('claim',queue='q',worker='x',now=6,lease=2,limit=2);assert [r['id']for r in rows]==['b'] and rows[0]['attempts']==2
assert rows[0]['receipt']!=old
before=db.read_bytes();reject('ack',queue='q',id='b',receipt=old,now=7);assert db.read_bytes()==before
stats=c('queue.stats',queue='q',now=8);assert stats['dead']==1 and stats['leased']==1
c('redrive',queue='q',id='b',now=8);r=c('claim',queue='q',worker='x',now=8,lease=3,limit=1)[0]
assert r['id']=='b' and r['attempts']==1;c('ack',queue='q',id='b',receipt=r['receipt'],now=9)
check('lease_expiry_dead_letter_redrive')
assert c('message.get',queue='q',id='b')['status']=='done'
c('message.publish',queue='q',id='c',payload=None,key='c');c('message.cancel',queue='q',id='c')
assert c('queue.stats',queue='q',now=20)=={'pending':1,'leased':0,'done':1,'dead':0,'cancelled':1}
check('completion_cancellation_restart')
before=db.read_bytes();reject('publish.import',messages=[{'queue':'q','id':'x','payload':0,'key':'batch'},{'queue':'missing','id':'y','payload':0,'key':'bad'}]);assert db.read_bytes()==before
reject('claim',queue='q',worker='x',now=21,lease=True,limit=1)
check('batch_and_types')
''')

add('subscriptions','Termine la gestion d’abonnements : plans, périodes, factures, changement d’offre, impayés et résiliation. Les montants et les renouvellements doivent rester exacts.',
'''## Deterministic subscription billing
plan.put {id,price:NONNEGATIVE_CENTS,period:POSITIVE_INT} upserts plan. subscriber.create
{id,plan,start:NONNEGATIVE_INT} unique subscriber, snapshots plan price/period. Return
{id,plan,status:'active',start,period_end:start+period,price,period,cancel_at_end:false,
balance:0,revision:1}. No charge at create. bill {id,now:NONNEGATIVE_INT,key} active/past_due,
now>=period_end; generate ONE invoice per fully elapsed billing period, each due at period_end,
amount=snapshotted price, advance start/end period-by-period until period_end>now. Return
{invoices:[{id:OPAQUE,subscriber,due,amount,paid:0}],subscriber:SNAPSHOT}. Global keys same
normalized request return ORIGINAL result and never bill twice; conflict rejects. A cancel_at_end
subscriber cancels at its first reached period_end WITHOUT a new invoice and doesn't advance
further; bill then returns invoices[] and cancelled status.
invoice.pay {id,amount:POSITIVE_CENTS,key} amount<=unpaid, globally idempotent with operation
and payload, add paid and reduce subscriber balance. subscriber status past_due iff balance>0,
else active (cancelled stays cancelled). subscriber.get {id}; invoice.list {subscriber} sorted
by (due,id). subscriber.change {id,plan,now,expected_revision} active only, exact revision,
start<=now<period_end, new plan same period length; snapshot new price. Proration difference
(new_price-old_price)*(period_end-now)//period, integer floor (including negative). Positive
adjustment creates invoice due now; negative adjustment decreases subscriber balance but not
below zero (credit not carried); return {subscriber,adjustment}. revision+1. New price applies
to future renewals. Prior invoices unchanged. subscriber.cancel {id,expected_revision}
active/past_due exact revision, set cancel_at_end true and revision+1; no immediate refund.
invoice.import_payments {payments:[{id,amount,key}]} all-or-none, return {imported:N}.
report {} -> {subscribers:COUNT,active:COUNT_ACTIVE,past_due:COUNT_PAST_DUE,cancelled:COUNT,
invoiced:SUM_INVOICE_AMOUNT,collected:SUM_PAID,outstanding:SUM_UNPAID}. Balance always equals
invoice unpaid totals (negative adjustment reduces existing unpaid invoice amounts in oldest
due order, never below paid). Restore validates snapshots, periods, money/statuses, references
and keys. Strict ints; concurrent bill same time without keys different cannot create duplicates.
''',r'''
c('plan.put',id='basic',price=100,period=10);c('plan.put',id='pro',price=200,period=10)
c('subscriber.create',id='s',plan='basic',start=0)
b=c('bill',id='s',now=20,key='bill');assert len(b['invoices'])==2 and b['subscriber']['period_end']==30
assert sum(x['amount']for x in b['invoices'])==200
assert c('bill',id='s',now=20,key='bill')==b
check('catchup_no_double_billing')
for row in b['invoices']:c('invoice.pay',id=row['id'],amount=100,key='p'+str(row['id']))
s=c('subscriber.get',id='s');assert s['status']=='active' and s['balance']==0
r=c('subscriber.change',id='s',plan='pro',now=25,expected_revision=s['revision']);assert r['adjustment']==50
assert c('subscriber.get',id='s')['balance']==50
check('payment_and_exact_proration')
s=c('subscriber.get',id='s');c('subscriber.cancel',id='s',expected_revision=s['revision'])
r=c('bill',id='s',now=30,key='end');assert r['invoices']==[] and r['subscriber']['status']=='cancelled'
assert c('report')['invoiced']==250 and c('report')['collected']==200
check('cancellation_and_reporting')
inv=c('invoice.list',subscriber='s')[-1];before=db.read_bytes();reject('invoice.import_payments',payments=[{'id':inv['id'],'amount':25,'key':'batch'},{'id':inv['id'],'amount':99,'key':'over'}]);assert db.read_bytes()==before
reject('plan.put',id='bad',price=True,period=10)
check('payment_batch_types')
''')

add('timesheets','Achève les feuilles de temps : chevauchements, budgets, validation séparée, verrouillage et export de facturation. Vérifie le parcours complet et les corrections.',
'''## Time tracking, approval and budgets
project.put {id,budget:NONNEGATIVE_MINUTES,rate:NONNEGATIVE_CENTS_PER_MINUTE} upserts project;
reject budget below total approved minutes (pending minutes don't reserve budget). worker.put
{id,role:'worker'/'manager'} upserts role. entry.create {id,worker,project,start:NONNEGATIVE_INT,
end:INT>start,note:NONEMPTY_TEXT} unique entry, worker/project exist. No overlapping active
entries for same worker across projects, half-open adjacency allowed. Return {id,worker,project,
start,end,note,status:'draft',revision:1,rate:CURRENT_PROJECT_RATE}. Snapshot rate at creation.
entry.edit {id,start,end,note,expected_revision} draft/rejected only, exact revision, overlap
checks ignoring self, status draft, revision+1. entry.submit {id,expected_revision} draft only,
exact revision, status submitted/revision+1. entry.review {id,actor,approve:BOOLEAN,
expected_revision} submitted only, actor manager different from entry.worker, exact revision.
If approve, atomically reserve duration from project budget and set approved, else rejected;
revision+1. Budget rejection leaves entry submitted/revision unchanged. entry.delete
{id,expected_revision} draft/rejected only, exact revision, removes and frees overlap interval.
entry.get {id}; entry.list {worker optional,project optional,status optional} sorted by(start,id).
period.lock {id,start,end} unique lock interval, no overlap with existing locks; all overlapping
entries must be approved, and no approved entry can straddle its boundaries. Locks prevent
create/edit/delete/review/submit touching their interval. invoice.export {lock} returns
{items:[{entry,worker,project,minutes,amount}],total:SUM_AMOUNT}, entries contained in lock,
sorted by entry ID, amount=minutes*snapshotted rate. project.report {id} returns
{approved:MINUTES,remaining:budget-approved,amount:APPROVED_SNAPSHOT_AMOUNT}.
entry.import {entries:[create-payloads]} all-or-none, including overlap among imported rows;
return {imported:N}. Restore validates references, intervals/statuses/revisions/rates, per-worker
non-overlap, approved budgets and lock invariants. Concurrent approvals cannot exceed budget.
''',r'''
c('project.put',id='p',budget=90,rate=2);c('worker.put',id='w',role='worker');c('worker.put',id='m',role='manager')
c('entry.create',id='e',worker='w',project='p',start=0,end=60,note='café')
reject('entry.create',id='over',worker='w',project='p',start=59,end=61,note='over')
c('entry.create',id='x',worker='w',project='p',start=60,end=120,note='x')
c('entry.submit',id='e',expected_revision=1);reject('entry.review',id='e',actor='w',approve=True,expected_revision=2)
c('entry.review',id='e',actor='m',approve=True,expected_revision=2)
check('overlap_submission_separation')
c('entry.submit',id='x',expected_revision=1);before=db.read_bytes();reject('entry.review',id='x',actor='m',approve=True,expected_revision=2);assert db.read_bytes()==before
c('entry.review',id='x',actor='m',approve=False,expected_revision=2)
c('entry.edit',id='x',start=60,end=90,note='trim',expected_revision=3);c('entry.submit',id='x',expected_revision=4);c('entry.review',id='x',actor='m',approve=True,expected_revision=5)
assert c('project.report',id='p')=={'approved':90,'remaining':0,'amount':180}
check('budget_rejection_and_repair')
c('project.put',id='p',budget=90,rate=99);c('period.lock',id='month',start=0,end=90)
r=c('invoice.export',lock='month');assert r['total']==180 and [x['entry']for x in r['items']]==['e','x']
reject('entry.create',id='locked',worker='m',project='p',start=1,end=2,note='bad')
reject('project.put',id='p',budget=89,rate=1)
check('immutable_lock_snapshot_billing')
before=db.read_bytes();reject('entry.import',entries=[{'id':'a','worker':'w','project':'p','start':100,'end':110,'note':'a'},{'id':'b','worker':'w','project':'p','start':105,'end':115,'note':'b'}]);assert db.read_bytes()==before
reject('entry.create',id='bool',worker='w',project='p',start=True,end=200,note='bad')
check('batch_and_types')
''')

add('documents','Finalise l’édition collaborative locale : versions, branches, fusion de champs, revues et publication. Les conflits ne doivent jamais écraser le travail existant.',
'''## Structured document branches and review
document.create {id,fields:OBJECT_STRING_KEYS_TO_STRING_VALUES} unique document; at least one
field and all keys nonempty, values may empty. Return {id,revision:1,fields,status:'draft',
approved:[],published:0}. document.edit {id,expected_revision,changes:OBJECT_OF_STRINGS}
exact revision, nonempty changes, update/add fields, revision+1, reset approved[], status draft.
branch.create {id,document} unique branch, snapshots document revision/fields as base and current
branch fields. Return {id,document,base_revision,revision:1,fields,status:'open'}.
branch.edit {id,expected_revision,changes} open/exact revision, update/add fields and revision+1.
branch.merge {id,expected_revision,document_revision} open branch exact branch/doc revisions;
three-way merge field-wise: for every field changed in branch from base, reject if document
also changed it to a DIFFERENT value; equal concurrent change is compatible. Unchanged branch
fields preserve live document edits. Entire merge atomic. Accepted merge increments document
revision once, clears approvals/status draft, branch status merged/revision+1. Return document.
branch.get {id}; document.get {id}. document.approve {id,actor,expected_revision} draft/approved,
exact revision, unique nonempty actor. Duplicate approval idempotent and no revision increase;
new approval DOES NOT change content revision. status approved when at least TWO different
actors, otherwise draft. document.publish {id,expected_revision} approved only/exact revision;
stores immutable current revision snapshot, published=current revision, status published.
Published documents may be edited, which creates a new draft revision while published snapshot
remains. document.live {id} returns {id,revision:LAST_PUBLISHED,fields:SNAPSHOT}, reject never
published. document.list {} sorted IDs. document.import {documents:[create-payloads]} all-or-none,
return {imported:N}. Restore validates document/branch IDs/revisions, string fields, base snapshots,
merged branch references/statuses, approval uniqueness and immutable published history.
Concurrent edits same revision have exactly one winner, and no successful merge loses a live edit.
''',r'''
c('document.create',id='d',fields={'title':'A','body':'B'})
c('branch.create',id='b',document='d');c('branch.edit',id='b',expected_revision=1,changes={'title':'Branch'})
c('document.edit',id='d',expected_revision=1,changes={'body':'Live'})
r=c('branch.merge',id='b',expected_revision=2,document_revision=2);assert r['fields']=={'title':'Branch','body':'Live'} and r['revision']==3
check('three_way_nonconflicting_merge')
c('branch.create',id='conflict',document='d');c('branch.edit',id='conflict',expected_revision=1,changes={'title':'X'})
c('document.edit',id='d',expected_revision=3,changes={'title':'Y'})
before=db.read_bytes();reject('branch.merge',id='conflict',expected_revision=2,document_revision=4);assert db.read_bytes()==before
c('document.approve',id='d',actor='a',expected_revision=4);reject('document.publish',id='d',expected_revision=4)
c('document.approve',id='d',actor='a',expected_revision=4);c('document.approve',id='d',actor='b',expected_revision=4)
c('document.publish',id='d',expected_revision=4)
check('conflict_and_separate_approvals')
c('document.edit',id='d',expected_revision=4,changes={'body':'New'})
assert c('document.live',id='d')['fields']=={'title':'Y','body':'Live'}
assert c('document.get',id='d')['approved']==[]
reject('document.edit',id='d',expected_revision=4,changes={'body':'stale'})
check('immutable_publication_and_cas')
before=db.read_bytes();reject('document.import',documents=[{'id':'x','fields':{'a':'b'}},{'id':'y','fields':{'a':1}}]);assert db.read_bytes()==before
reject('branch.merge',id='b',expected_revision=3,document_revision=5)
check('atomic_import_and_closed_branch')
''')

add('warehouse','Termine la logistique par lots : réceptions, péremption, allocations FEFO, expéditions partielles et retours. Vérifie les parcours et la cohérence des stocks.',
'''## Lot-aware stock and fulfillment
product.put {id,name} upserts product. lot.receive {id,product,quantity:POSITIVE_INT,
expires:NONNEGATIVE_INT,key} unique lot, known product. Global idempotent key same normalized
request/operation returns original snapshot; conflicts reject. Return {id,product,on_hand:quantity,
reserved:0,expires}. order.create {id,lines:[{product,quantity:POSITIVE_INT}]} unique order,
nonempty lines, aggregate duplicates sorted product, all products exist. Return
{id,status:'draft',lines,allocations:[],shipped:[],returned:[]}.
order.allocate {id,now:NONNEGATIVE_INT} draft only; greedily allocate each product from lots
where expires>now, sorted by(expires,lot_id), quantity<=on_hand-reserved. Reject all if any line
short; no reservations left on failure. Set confirmed, allocations [{lot,quantity}] sorted by lot.
Repeated allocate confirmed returns same snapshot. order.ship {id,lines:[{lot,quantity}],key}
confirmed/partial, aggregate duplicates, <=allocated minus shipped. Atomically reduce on_hand
AND reserved, add cumulative sorted shipped lines; status shipped when all sent else partial.
order.cancel {id} draft/confirmed/partial, idempotent cancelled; release unshipped reservations,
keep historical shipments; fully shipped cannot cancel. order.return {id,lines,key} quantities
<=shipped minus returned, atomically increase original lot on_hand, reservations unchanged;
accumulate returned, preserve order status. Global keys across receive/ship/return, original
snapshot replay even after order changes. order.get {id}; lot.list {product optional,now optional}
sorted by(expires,id), optional now filters expires>now only; include {id,product,on_hand,
reserved,available:on_hand-reserved,expires}. stock.report {product,now} -> {on_hand:ALL_LOTS,
reserved:ALL_LOTS,available:NONEXPIRED_FREE,expired:EXPIRED_ON_HAND}.
lot.import {lots:[receive-payloads]} all-or-none, return {imported:N}. Restore validates all
references, nonnegative stock/capacity, allocation/shipment/return history and aggregate reservation
invariants, statuses and idempotency. Concurrent orders cannot overreserve a lot. Logical expiry
only affects new allocations; already reserved lots can ship after expiry.
''',r'''
c('product.put',id='p',name='Milk')
c('lot.receive',id='late',product='p',quantity=5,expires=20,key='late');c('lot.receive',id='early',product='p',quantity=2,expires=10,key='early')
c('order.create',id='o',lines=[{'product':'p','quantity':4}]);r=c('order.allocate',id='o',now=0)
assert r['allocations']==[{'lot':'early','quantity':2},{'lot':'late','quantity':2}]
assert c('stock.report',product='p',now=0)=={'on_hand':7,'reserved':4,'available':3,'expired':0}
check('fefo_allocation')
c('order.create',id='short',lines=[{'product':'p','quantity':4}]);before=db.read_bytes();reject('order.allocate',id='short',now=0);assert db.read_bytes()==before
r=c('order.ship',id='o',lines=[{'lot':'early','quantity':1}],key='ship');assert r['status']=='partial'
assert c('order.ship',id='o',lines=[{'lot':'early','quantity':1}],key='ship')==r
c('order.cancel',id='o');c('order.return',id='o',lines=[{'lot':'early','quantity':1}],key='return')
assert c('stock.report',product='p',now=10)=={'on_hand':7,'reserved':0,'available':5,'expired':2}
check('partial_cancel_return_expiry')
reject('order.return',id='o',lines=[{'lot':'early','quantity':1}],key='twice')
c('order.create',id='next',lines=[{'product':'p','quantity':5}]);c('order.allocate',id='next',now=10)
assert c('order.get',id='next')['allocations']==[{'lot':'late','quantity':5}]
check('bounded_returns_no_expired_allocations')
before=db.read_bytes();reject('lot.import',lots=[{'id':'x','product':'p','quantity':1,'expires':30,'key':'batch'},{'id':'y','product':'none','quantity':1,'expires':30,'key':'bad'}]);assert db.read_bytes()==before
reject('lot.receive',id='bool',product='p',quantity=True,expires=30,key='bool')
check('batch_and_strict_quantity')
''')

add('annotations','Achève l’annotation de données : jeux, affectations sous bail, votes indépendants, consensus et réouverture. Les contributions et les droits doivent survivre à la reprise.',
'''## Dataset annotation with independent reviewers
dataset.create {id,labels:[STRINGS],reviews:POSITIVE_INT} unique dataset; nonempty normalized
labels. annotator.put {id,active:BOOLEAN} creates/upserts reviewer; deactivation prevents claims
and submissions but preserves history. item.add {dataset,id,payload:JSON_VALUE} unique ID within
dataset. Return {id,dataset,payload,status:'pending',votes:[],revision:1,consensus:null}.
claim {dataset,annotator,now:NONNEGATIVE_INT,lease:POSITIVE_INT} active known annotator; chooses
lexical first pending/reviewing item with fewer than required votes, annotator hasn't voted,
and no unexpired claim by that annotator on it. Different annotators may claim the same item
only if votes+live claims<reviews, preventing overclaim. Return null if none, otherwise
{item,receipt:NEW_OPAQUE,expires:now+lease}; each claim receipt unique across restarts.
submit {dataset,item,annotator,receipt,now,label} current unexpired claim, active annotator,
known label, one vote per annotator. Append {annotator,label} in submission order, revision+1,
release claim. With required vote count, status complete; consensus is label only if all votes
agree, otherwise null. Before complete status reviewing. Claims expire at now>=expires and
may be replaced without counting as votes; stale receipts always reject, no side effects.
item.reopen {dataset,id,expected_revision} complete only/exact revision, clears votes/claims/
consensus, status pending, revision+1; retain prior completed vote rounds in immutable history.
item.get {dataset,id}; item.list {dataset,status optional} sorted IDs. history {dataset,id}
returns prior rounds in completion order, each {votes,consensus}; reopening records one round.
report {dataset} -> {pending:COUNT,reviewing:COUNT,complete:COUNT,disputed:COUNT_COMPLETE_NULL}.
item.import {dataset,items:[{id,payload}]} all-or-none, return {imported:N}. Restore validates
all references/statuses/revisions/vote uniqueness/known labels, consensus, live claim ownership/
receipt uniqueness/capacity and histories. Concurrent claims/submissions cannot overfill reviews.
''',r'''
c('dataset.create',id='d',labels=['yes','no'],reviews=2)
for who in ['a','b','c']:c('annotator.put',id=who,active=True)
c('item.add',dataset='d',id='i',payload={'café':1})
a=c('claim',dataset='d',annotator='a',now=0,lease=10);b=c('claim',dataset='d',annotator='b',now=0,lease=10)
assert a['item']=='i' and b['item']=='i' and a['receipt']!=b['receipt']
assert c('claim',dataset='d',annotator='c',now=1,lease=10) is None
c('submit',dataset='d',item='i',annotator='a',receipt=a['receipt'],now=2,label='yes')
check('bounded_independent_claims')
before=db.read_bytes();reject('submit',dataset='d',item='i',annotator='b',receipt=b['receipt'],now=10,label='yes');assert db.read_bytes()==before
new=c('claim',dataset='d',annotator='c',now=10,lease=10);assert new['receipt']!=b['receipt']
c('submit',dataset='d',item='i',annotator='c',receipt=new['receipt'],now=11,label='no')
r=c('item.get',dataset='d',id='i');assert r['status']=='complete' and r['consensus'] is None
assert c('report',dataset='d')['disputed']==1
check('expiry_stale_receipt_disagreement')
c('item.reopen',dataset='d',id='i',expected_revision=r['revision'])
assert c('history',dataset='d',id='i')[0]['consensus'] is None
assert c('item.get',dataset='d',id='i')['votes']==[]
c('annotator.put',id='a',active=False);reject('claim',dataset='d',annotator='a',now=20,lease=1)
check('reopen_history_and_deactivation')
before=db.read_bytes();reject('item.import',dataset='d',items=[{'id':'x','payload':1},{'id':'i','payload':2}]);assert db.read_bytes()==before
reject('dataset.create',id='bad',labels=['x'],reviews=True)
check('batch_and_types')
''')

add('vault','Termine ce coffre documentaire local : espaces, rôles, versions, quotas, suppression et restauration. Les droits doivent s’appliquer à tous les parcours et rester cohérents.',
'''## Workspace document vault (synthetic identities, no real credentials)
workspace.create {id,owner,quota:NONNEGATIVE_BYTES} unique workspace, owner nonempty user ID,
initial owner admin. member.put {workspace,actor,user,role:'admin'/'editor'/'viewer'} admin actor,
upserts membership, cannot demote/remove last admin. member.remove {workspace,actor,user}
admin only, same last-admin rule. document.put {workspace,actor,id,content:STRING,
expected_revision:NONNEGATIVE_INT} admin/editor, unique ID on first put expected_revision0,
updates exact current revision thereafter. UTF8 byte size counts toward workspace quota across
ALL retained versions, including deleted documents. Each accepted put creates immutable version
number current+1 and returns {id,revision,content,deleted:false,size:UTF8_BYTES}. Updating a deleted
document rejects until restored. Empty content allowed. No cross-workspace membership leakage.
document.get {workspace,actor,id,revision optional} any member, current or historical version;
deleted documents cannot be read except admin. Version returns {id,revision,content,deleted:CURRENT_DELETION,
size}. document.delete {workspace,actor,id,expected_revision} admin/editor, live/exact revision,
soft deletes without version/revision increase; repeated delete rejects. document.restore
{workspace,actor,id} admin only, deleted only, restores live without new version.
document.purge {workspace,actor,id} admin only, deleted only, removes all versions and releases quota.
document.list {workspace,actor,include_deleted optionalfalse} sorted current docs; viewers/editors
cannot set include_deleted true. quota.set {workspace,actor,quota} admin, can't reduce below used.
quota.get {workspace,actor} any member -> {quota,used,available}. document.import
{workspace,actor,documents:[{id,content}]} admin only, atomically create whole batch with quota,
existing/repeated IDs reject; return {imported:N}. Restore(whole service) validates member roles,
last admins, version sequence/content sizes/current revision/deletion, used quotas and references.
Rejected requests preserve data-file bytes. Concurrent puts same revision have one winner.
''',r'''
c('workspace.create',id='w',owner='admin',quota=10)
c('member.put',workspace='w',actor='admin',user='editor',role='editor');c('member.put',workspace='w',actor='admin',user='view',role='viewer')
a=c('document.put',workspace='w',actor='editor',id='d',content='été',expected_revision=0);assert a['size']==5 and a['revision']==1
reject('document.put',workspace='w',actor='view',id='x',content='x',expected_revision=0)
c('document.put',workspace='w',actor='editor',id='d',content='abc',expected_revision=1)
assert c('quota.get',workspace='w',actor='view')=={'quota':10,'used':8,'available':2}
check('roles_utf8_version_quota')
assert c('document.get',workspace='w',actor='view',id='d',revision=1)['content']=='été'
before=db.read_bytes();reject('document.put',workspace='w',actor='editor',id='d',content='xyz',expected_revision=2);assert db.read_bytes()==before
c('document.delete',workspace='w',actor='editor',id='d',expected_revision=2)
reject('document.get',workspace='w',actor='view',id='d')
c('document.restore',workspace='w',actor='admin',id='d');assert c('document.get',workspace='w',actor='view',id='d')['revision']==2
check('immutable_history_soft_delete')
c('document.delete',workspace='w',actor='admin',id='d',expected_revision=2);c('document.purge',workspace='w',actor='admin',id='d')
assert c('quota.get',workspace='w',actor='view')['used']==0
reject('member.remove',workspace='w',actor='admin',user='admin')
c('workspace.create',id='other',owner='stranger',quota=10);reject('document.list',workspace='other',actor='view')
check('purge_last_admin_isolation')
before=db.read_bytes();reject('document.import',workspace='w',actor='admin',documents=[{'id':'x','content':'x'},{'id':'y','content':'z'*20}]);assert db.read_bytes()==before
reject('quota.set',workspace='w',actor='admin',quota=True)
check('quota_atomic_batch_types')
''')

add('etl','Achève ce pipeline d’import de données : schémas, CSV, normalisation exacte, rejets, déduplication et publication atomique. Vérifie les étapes et la traçabilité.',
'''## Versioned CSV normalization jobs
schema.put {id,columns:[{name,type:'text'/'integer'/'money',required:BOOLEAN}],key:PRIMARY_COLUMN}
creates/replaces schema revision+1; unique nonempty column names, key must be required text column.
Return {id,revision,columns,key}. job.create {id,schema,csv:STRING} unique job, snapshots current
schema, stores raw input, status draft. CSV header must match column names in exact order,
quoting/newlines/Unicode supported; validate header BEFORE committing creation. job.run {id,key}
draft only, global idempotency same operation/payload original result, conflict rejects. Process
rows in order: trim all cells; required text nonempty; integer optional empty ->null else strict
signed base10 integer text (no decimal/exponent/bool); money optional empty->null else nonnegative
decimal with at most TWO fractional digits, convert exactly to integer cents (no floats).
Missing/extra cells, invalid values, empty primary key or duplicate valid key reject that row.
First VALID row for a key wins; invalid earlier row doesn't reserve key. Return
{id,status:'processed',accepted:N,rejected:N,rows:[NORMALIZED_OBJECTS],rejects:[{row:CSV_LINE,
reason:NONEMPTY}],schema_revision:SNAPSHOT_REVISION}. row uses csv.reader.line_num including
physical embedded-newline lines, captured after reading current row. No partial publication.
job.publish {id,expected_revision:1} processed only, once; set published/revision2 and replace
schema's current published dataset atomically with normalized rows. job.get {id} includes
revision (initial1), result fields after run, original input stays available as csv.
dataset.get {schema} returns {job:LAST_PUBLISHED_ID,rows:SNAPSHOT,schema_revision}; reject no
publication. job.export {id} processed/published returns CSV string with original column names,
normalized integers/cents rendered as integer decimal strings, null empty, original row order.
job.retry {id,csv:STRING} processed but not published only, validate header against SNAPSHOT,
replace input and reset draft/result, revision stays1; old run keys retain original result.
job.import {jobs:[{id,schema,csv}]} all-or-none, return {imported:N}. Restore validates schema
column types/revisions, job snapshots/results/counts/keys, dataset publication references and
normalized types. New schema changes don't reinterpret an existing job.
''',r'''
import csv,io
cols=[{'name':'id','type':'text','required':True},{'name':'qty','type':'integer','required':True},{'name':'price','type':'money','required':True}]
c('schema.put',id='s',columns=cols,key='id')
raw='id,qty,price\na,3,0.10\na,1,99\nb,x,2\nb,2,1.25\nc,1,1.999\n'
c('job.create',id='j',schema='s',csv=raw);r=c('job.run',id='j',key='run')
assert (r['accepted'],r['rejected'])==(2,3)
assert r['rows']==[{'id':'a','qty':3,'price':10},{'id':'b','qty':2,'price':125}]
assert [x['row']for x in r['rejects']]==[3,4,6]
assert c('job.run',id='j',key='run')==r
check('normalization_exact_money_dedup')
c('schema.put',id='s',columns=cols,key='id');assert c('job.get',id='j')['schema_revision']==1
c('job.publish',id='j',expected_revision=1);assert c('dataset.get',schema='s')['rows']==r['rows']
rows=list(csv.DictReader(io.StringIO(c('job.export',id='j'))));assert rows[0]['price']=='10' and rows[1]['qty']=='2'
reject('job.retry',id='j',csv=raw)
check('schema_snapshot_publication_export')
c('job.create',id='retry',schema='s',csv='id,qty,price\nx,bad,1\n');c('job.run',id='retry',key='retry1')
c('job.retry',id='retry',csv='id,qty,price\nx,1,1\n');assert c('job.run',id='retry',key='retry2')['accepted']==1
check('retry_independent_receipts')
before=db.read_bytes();reject('job.import',jobs=[{'id':'x','schema':'s','csv':raw},{'id':'y','schema':'s','csv':'bad,header\n1,2\n'}]);assert db.read_bytes()==before
reject('job.publish',id='retry',expected_revision=True)
check('atomic_header_batch_types')
''')

add('loyalty','Termine ce programme de fidélité : crédits expirables, consommation prioritaire, réservations, remboursements et ajustements. Aucun solde négatif ni crédit perdu.',
'''## Expiring points and reservations
member.create {id} unique member. earn {member,id,points:POSITIVE_INT,expires:NONNEGATIVE_INT,key}
unique earning lot ID globally, global idempotency same normalized payload original snapshot,
changed request/operation rejects. Return {id,member,points,remaining:points,expires}.
balance {member,now:NONNEGATIVE_INT} -> {available:UNEXPIRED_UNRESERVED,held:ACTIVE_HOLD_POINTS,
expired:REMAINING_EXPIRED_UNRESERVED}. Lots with expires<=now cannot supply new redemption.
hold {member,id,points:POSITIVE_INT,now,ttl:POSITIVE_INT} unique hold, atomically allocate from
unexpired free lots sorted by(expires,id), no partial hold. Return {id,member,points,status:'held',
expires:now+ttl,allocations:[{lot,points}]}. Active held points remain held until their hold
expires, even if earning lot expires meanwhile. All operations using now lazily release expired
HOLDS at now>=hold.expires; rejected operations must not commit that cleanup.
redeem {id,now,key} unexpired held hold only, consume its reserved lot remaining, set redeemed,
return {id,member,points,status:'redeemed',refunded:0}. Global keys permit original snapshot
replay even after refund/expiry, conflict rejects. release {id,now} held only, set released,
idempotent after released; frees reservations but doesn't restore expired lot validity.
refund {id,points:POSITIVE_INT,now,key} redeemed only, cumulative <=redeemed points; restores
points to original earning lots in REVERSE allocation order, up to originally consumed quantities,
without extending lot expiry; increase refunded. Return redemption snapshot. Global keys across
earn/redeem/refund. lot.list {member} sorted by(expires,id); hold.get {id,now} returns hold,
reflecting expiry status 'expired' when reached. history {member} insertion-ordered successful
non-replayed earn/redeem/refund events {kind,id,points}, no hold/release events.
earn.import {earnings:[earn-payloads]} all-or-none, return {imported:N}. Restore validates members,
points/lots/reservations/redemption/refund allocation bounds, statuses/time and global keys;
concurrent holds cannot overreserve. Strict integers and no automatic resurrection of expired lots.
''',r'''
c('member.create',id='m');a=c('earn',member='m',id='early',points=50,expires=10,key='early');c('earn',member='m',id='late',points=70,expires=30,key='late')
assert c('earn',member='m',id='early',points=50,expires=10,key='early')==a
h=c('hold',member='m',id='h',points=80,now=0,ttl=20);assert h['allocations']==[{'lot':'early','points':50},{'lot':'late','points':30}]
assert c('balance',member='m',now=11)=={'available':40,'held':80,'expired':0}
check('expiry_order_holds')
r=c('redeem',id='h',now=12,key='redeem');assert r['status']=='redeemed'
assert c('redeem',id='h',now=12,key='redeem')==r
c('refund',id='h',points=40,now=13,key='refund')
assert c('balance',member='m',now=13)=={'available':70,'held':0,'expired':10}
reject('refund',id='h',points=41,now=13,key='over')
check('bounded_refund_original_expiry')
c('hold',member='m',id='expire',points=10,now=13,ttl=2)
assert c('hold.get',id='expire',now=15)['status']=='expired'
reject('redeem',id='expire',now=15,key='expired')
assert [x['kind']for x in c('history',member='m')]==['earn','earn','redeem','refund']
check('hold_expiry_history')
before=db.read_bytes();reject('earn.import',earnings=[{'member':'m','id':'x','points':1,'expires':50,'key':'batch'},{'member':'missing','id':'y','points':1,'expires':50,'key':'bad'}]);assert db.read_bytes()==before
reject('hold',member='m',id='bool',points=True,now=15,ttl=1)
check('batch_and_strict_points')
''')

add('manufacturing','Achève la production locale : nomenclatures, composants, réservations, fabrication partielle, rebuts et annulations. Vérifie la conservation des quantités et des coûts.',
'''## Bill-of-materials manufacturing
part.put {id,name,cost:NONNEGATIVE_CENTS} upserts part; new part stock0. bom.put
{product,components:[{part,quantity:POSITIVE_INT}]} product and parts exist, nonempty component
list, aggregate duplicate parts, no self/transitive cycle across BOMs; revision increments.
Manufacturing consumes DIRECT BOM components only (not recursive expansion), finished product
may itself be a component in another BOM. receive {part,quantity:POSITIVE_INT,key} globally
idempotent same normalized request original {on_hand}; conflicts reject, increases stock.
work.create {id,product,quantity:POSITIVE_INT} unique work order, requires BOM, snapshots BOM
and costs, return {id,product,quantity,produced:0,scrapped:0,status:'draft',reserved:[],cost:0}.
work.reserve {id} draft only; atomically reserve full required direct component quantities from
available on_hand-reserved; all-or-none. confirmed if success, reserved sorted [{part,quantity}].
Repeated reserve confirmed idempotent. work.finish {id,good:NONNEGATIVE_INT,scrap:NONNEGATIVE_INT,
key} confirmed/partial only, good+scrap>0, <=quantity-produced-scrapped. Atomically consume
snapshotted component quantities for good+scrap, reduce reservations/on_hand, increase finished
product stock by good only, produced+=good, scrapped+=scrap. cost adds consumed components'
snapshotted unit costs for good AND scrap. Status complete when all units attempted else partial.
Global key original result replay, operation/payload conflicts reject. work.cancel {id}
draft/confirmed/partial only, idempotent cancelled; release remaining reservations, preserve
production/scrap/cost history; complete cannot cancel. work.get {id}; stock {part} ->
{on_hand,reserved,available}. work.list {status optional} sorted IDs. receive.import
{receipts:[receive-payloads]} all-or-none, return {imported:N}. Restore validates BOM DAGs,
references, capacities, work snapshots, consumption/production/scrap/cost histories and keys.
Live BOM/cost edits don't change existing orders. Concurrent reservations cannot oversubscribe.
''',r'''
for part,cost in [('wood',10),('screw',2),('chair',0)]:c('part.put',id=part,name=part,cost=cost)
c('bom.put',product='chair',components=[{'part':'wood','quantity':2},{'part':'screw','quantity':4}])
c('receive',part='wood',quantity=10,key='wood');c('receive',part='screw',quantity=20,key='screws')
c('work.create',id='w',product='chair',quantity=3);c('work.reserve',id='w')
assert c('stock',part='wood')=={'on_hand':10,'reserved':6,'available':4}
check('bom_reservation')
c('part.put',id='wood',name='wood',cost=99);c('bom.put',product='chair',components=[{'part':'wood','quantity':1}])
r=c('work.finish',id='w',good=1,scrap=1,key='finish');assert r['produced']==1 and r['scrapped']==1 and r['cost']==56 and r['status']=='partial'
assert c('work.finish',id='w',good=1,scrap=1,key='finish')==r
assert c('stock',part='chair')['on_hand']==1
check('partial_scrap_snapshot_cost')
c('work.cancel',id='w');assert c('stock',part='wood')=={'on_hand':6,'reserved':0,'available':6}
reject('work.finish',id='w',good=1,scrap=0,key='late')
reject('bom.put',product='wood',components=[{'part':'chair','quantity':1}])
check('cancellation_and_cycles')
before=db.read_bytes();reject('receive.import',receipts=[{'part':'wood','quantity':1,'key':'batch'},{'part':'missing','quantity':1,'key':'bad'}]);assert db.read_bytes()==before
reject('work.create',id='bool',product='chair',quantity=True)
check('batch_types')
''')

add('voting','Termine cet outil de décisions d’association : membres, scrutins, délégations, bulletins classés, quorum et dépouillement vérifiable. Préserve l’intégrité de chaque tour.',
'''## Offline ranked-choice association decisions (synthetic members)
member.put {id,active:BOOLEAN} upserts member; deactivation allowed but does not remove already
cast ballots. poll.create {id,candidates:[IDS],quorum:POSITIVE_INT} unique poll, >=2 distinct
nonempty candidates normalized sorted, draft/revision1. poll.open {id,expected_revision} draft
only/exact revision; snapshots currently active eligible member IDs, status open/revision+1.
Membership edits after opening don't alter eligibility. delegate {poll,member,to} both eligible,
member!=to, poll open, member has no ballot, no transitive delegation cycle. Delegation replaces
previous choice; a delegated member cannot cast until undelegate. undelegate {poll,member}
open, removes existing delegation. vote {poll,member,ranking:[CANDIDATE_IDS],key} open, eligible,
member not delegated, ranking nonempty unique subset of candidates in preference order. One
ballot per member; global idempotency same normalized request original result, conflict rejects.
Return {poll,member,ranking}. Voting doesn't stop other eligible members delegating to voter.
poll.close {id,expected_revision} open/exact revision; snapshot ballots/delegations, mark closed,
revision+1. tally {poll} closed only -> {quorum_met,participating,winner:ID_OR_NULL,rounds:[...]}
Each eligible member contributes weight1 to its own ballot or follows delegation transitively
to a member with a ballot; missing ballot at terminal delegate means no participation. Compute
instant-runoff: in each round count each represented voter's highest still-active ranked candidate;
return {counts:{ACTIVE_CANDIDATE:INT},exhausted:INT,eliminated:ID_OR_NULL}. Winner if strictly
more than half non-exhausted votes; if one candidate remains it wins only if non-exhausted>0.
Otherwise eliminate the lowest-count candidate, breaking ties by LEXICALLY GREATEST candidate,
and continue. If quorum not met or all ballots exhausted, winner null (may return rounds[] when
quorum fails). poll.get {id}; poll.list {} sorted IDs. vote.import {votes:[vote-payloads]}
all-or-none, return {imported:N}. Restore validates poll states/revisions/eligibility snapshots,
ballot rankings/unique voters/keys/delegation references and acyclicity; closed results stable.
''',r'''
for who in ['a','b','c','d']:c('member.put',id=who,active=True)
c('poll.create',id='p',candidates=['X','Y','Z'],quorum=3);c('poll.open',id='p',expected_revision=1)
c('member.put',id='a',active=False)
c('delegate',poll='p',member='d',to='a');reject('delegate',poll='p',member='a',to='d')
a=c('vote',poll='p',member='a',ranking=['X','Y'],key='a');assert c('vote',poll='p',member='a',ranking=['X','Y'],key='a')==a
c('vote',poll='p',member='b',ranking=['Y','X'],key='b');c('vote',poll='p',member='c',ranking=['Z','Y'],key='c')
check('eligibility_delegation_and_votes')
c('poll.close',id='p',expected_revision=2);r=c('tally',poll='p');assert r['quorum_met'] and r['participating']==4
assert r['rounds'][0]['counts']=={'X':2,'Y':1,'Z':1} and r['rounds'][0]['eliminated']=='Z'
assert r['winner']=='X'
reject('vote',poll='p',member='d',ranking=['X'],key='late')
check('weighted_irv_lexical_tie')
c('poll.create',id='q',candidates=['X','Y'],quorum=3);c('poll.open',id='q',expected_revision=1)
c('vote',poll='q',member='b',ranking=['X'],key='q')
c('poll.close',id='q',expected_revision=2);assert not c('tally',poll='q')['quorum_met'] and c('tally',poll='q')['winner'] is None
check('quorum_separate_polls')
c('poll.create',id='batch',candidates=['X','Y'],quorum=1);c('poll.open',id='batch',expected_revision=1)
before=db.read_bytes();reject('vote.import',votes=[{'poll':'batch','member':'b','ranking':['X'],'key':'batch'},{'poll':'batch','member':'c','ranking':['BAD'],'key':'bad'}]);assert db.read_bytes()==before
reject('poll.create',id='bool',candidates=['X','Y'],quorum=True)
check('batch_and_types')
''')


def materialize(name,repo):
 repo=Path(repo);repo.mkdir(parents=True)
 (repo/'README.md').write_text(COMMON+CASES[name]['spec'])
 (repo/'app.py').write_text("def banner():return 'Local Ops — café'\n\nclass Service:\n def __init__(self,path):self.path=path\n def call(self,operation,data):raise ValueError('Not implemented')\n")
 (repo/'USER_NOTES.txt').write_bytes('Original customer data: café 東京\nPreserve this document.\n'.encode())
 (repo/'tests').mkdir();(repo/'tests/__init__.py').write_text('')
 (repo/'tests/test_legacy.py').write_text("import unittest\nfrom app import banner\nclass Legacy(unittest.TestCase):\n def test_banner(self):self.assertEqual(banner(),'Local Ops — café')\n")
 return CASES[name]['goal']


def judge_program(name):
 text='''import copy,csv,hashlib,io,json,os,subprocess,sys,tempfile
from pathlib import Path
repo=Path(sys.argv[1]);sys.path.insert(0,str(repo))
import app as m
passed=[]
def check(group):passed.append(group);print('PASS',group,flush=True)
with tempfile.TemporaryDirectory(prefix='gp-judge-') as tmp:
 db=Path(tmp)/'data.json'
 def c(operation,**data):
  original=copy.deepcopy(data)
  value=m.Service(db).call(operation,data)
  assert data==original,'Application modified caller input'
  json.dumps(value,allow_nan=False)
  return value
 def reject(operation,**data):
  before=db.read_bytes() if db.exists() else None
  original=copy.deepcopy(data)
  try:m.Service(db).call(operation,data)
  except ValueError:pass
  else:raise AssertionError('Invalid request accepted: '+operation)
  assert data==original,'Rejected request changed caller input'
  assert (db.read_bytes() if db.exists() else None)==before,'Rejected request changed persisted data'
'''
 text+='\n'.join(' '+line for line in CASES[name]['judge'].splitlines())+'\n'
 from races import program
 text+=program(name)
 text+=''' snapshot=c('backup');original=copy.deepcopy(snapshot)
 snapshot['__judge_detachment_probe__']=True
 assert c('backup')==original,'Backup aliases live state'
 check('detached_snapshots_and_restart')
 reject('restore',state=[]);reject('restore',state={'__invalid_service_state__':True})
 c('restore',state=original);assert c('backup')==original
 check('restore_rejects_invalid_without_data_loss')
 argv=[sys.executable,str(repo/'app.py'),'--file',str(db)]
 packets=[{'operation':'backup','data':{}},{'operation':'__unknown_operation__','data':{}},[],{'operation':'backup','data':{}}]
 raw='bad-json\\n'+''.join(json.dumps(x,ensure_ascii=False)+'\\n'for x in packets)
 result=subprocess.run([*argv,'jsonl'],input=raw,text=True,capture_output=True,timeout=15,cwd=repo)
 assert result.returncode==0,result.stderr
 rows=[json.loads(line)for line in result.stdout.splitlines()]
 assert len(rows)==5 and [r['ok']for r in rows]==[False,True,False,False,True],rows
 assert rows[1]['result']==rows[4]['result']==original
 assert all(rows[i].get('error')for i in (0,2,3))
 check('real_jsonl_errors_and_recovery')
 from host_helpers import json_http
 with json_http([*argv,'serve','--port','0'],cwd=repo) as request:
  assert request('GET','/health')=={'ok':True}
  assert request('POST','/api',{'operation':'backup','data':{}})=={'ok':True,'result':original}
  assert request('POST','/api',[],status=400).get('ok') is False
  assert request('POST','/api',{'operation':'__unknown_operation__'},status=400).get('ok') is False
  assert request('GET','/not-a-path',status=404).get('ok') is False
 check('real_http_domain_errors_health')
 assert c('backup')==original
 assert (repo/'USER_NOTES.txt').read_bytes()=='Original customer data: café 東京\\nPreserve this document.\\n'.encode()
 assert m.banner()=='Local Ops — café'
 check('original_behavior_and_customer_data')
'''
 return text


def judge(name,repo,dest):
 dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
 script=dest/'judge.py';script.write_text(judge_program(name))
 sys.path.insert(0,str(Path(__file__).resolve().parent))
 from host_process import run_process
 result=run_process([sys.executable,'-B',str(script),str(repo)],Path(repo),90,
   env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parent),'PYTHONOPTIMIZE':'0'},log_path=dest/'judge.log')
 groups=[line[5:]for line in result.output.splitlines()if line.startswith('PASS ')]
 return {'correct':result.returncode==0 and len(groups)==10,'returncode':result.returncode,'timed_out':result.timed_out,'seconds':result.duration_seconds,'groups_passed':groups}

if __name__=='__main__':
 assert len(CASES)==20
 out=[]
 for name in CASES:
  compile(judge_program(name),'<judge-'+name+'>','exec')
  with tempfile.TemporaryDirectory()as tmp:
   repo=Path(tmp)/'repo';materialize(name,repo);r=judge(name,repo,Path(tmp)/'judge')
   assert not r['correct'];out.append({'case':name,'judge_compiles':True,'unimplemented_starter_rejected':True,'public_operations':CASES[name]['spec'].count(' {'),'contract_bytes':len((COMMON+CASES[name]['spec']).encode()),'groups':10})
 print(json.dumps(out,indent=2))
