from goalpilot_runtime import ReplayService, require, text, integer, boolean, fields, sequence, choice, get_record


def banner():return 'Local Ops — café'


class Service(ReplayService):
 def initial(self):return {'workspaces':{}}
 def handle(self,state,op,data):
  txt=lambda x:require(isinstance(x,str),'Expected string')
  base={'workspace':text,'actor':text}
  specs={
   'workspace.create':{'id':text,'owner':text,'quota':integer},
   'member.put':dict(base,user=text,role=choice('admin','editor','viewer')),
   'member.remove':dict(base,user=text),
   'document.put':dict(base,id=text,content=txt,expected_revision=integer),
   'document.get':dict(base,id=text),
   'document.delete':dict(base,id=text,expected_revision=integer),
   'document.restore':dict(base,id=text),'document.purge':dict(base,id=text),
   'document.list':base,'quota.set':dict(base,quota=integer),'quota.get':base,
   'document.import':dict(base,documents=sequence(fields_validator:=lambda x:fields(x,{'id':text,'content':txt}))) }
  require(op in specs,'Unknown operation')
  optional={'revision':lambda x:integer(x,minimum=1)} if op=='document.get' else {'include_deleted':boolean} if op=='document.list' else None
  fields(data,specs[op],optional)
  spaces=state['workspaces']
  if op=='workspace.create':
   require(data['id'] not in spaces,'Workspace exists')
   spaces[data['id']]={'members':{data['owner']:'admin'},'quota':data['quota'],'documents':{}}
   return {'id':data['id'],'owner':data['owner'],'quota':data['quota']}
  w=get_record(spaces,data['workspace']); role=w['members'].get(data['actor'])
  require(role is not None,'Membership required')
  docs=w['documents']
  used=lambda:sum(v['size'] for d in docs.values() for v in d['versions'])
  def admin():require(role=='admin','Admin required')
  def view(id,d,revision=None):
   v=d['versions'][(revision or len(d['versions']))-1]
   return dict(id=id,revision=v['revision'],content=v['content'],deleted=d['deleted'],size=v['size'])
  def version(content,n):return {'revision':n,'content':content,'size':len(content.encode('utf-8'))}
  if op.startswith('member.'):
   admin(); user=data['user']; members=w['members']
   if op=='member.remove':require(user in members,'Missing member')
   if members.get(user)=='admin' and (op=='member.remove' or data['role']!='admin'):
    require(list(members.values()).count('admin')>1,'Last admin')
   if op=='member.remove':del members[user]
   else:members[user]=data['role']
   return {'user':user,'role':members.get(user)}
  if op=='quota.get':return {'quota':w['quota'],'used':used(),'available':w['quota']-used()}
  if op=='quota.set':
   admin(); require(data['quota']>=used(),'Quota below usage'); w['quota']=data['quota']
   return {'quota':w['quota'],'used':used(),'available':w['quota']-used()}
  if op=='document.list':
   include=data.get('include_deleted',False)
   if include:admin()
   return [view(id,d) for id,d in sorted(docs.items()) if include or not d['deleted']]
  if op=='document.import':
   admin(); batch=data['documents']; ids=[d['id'] for d in batch]
   require(len(set(ids))==len(ids) and not set(ids).intersection(docs),'Duplicate document')
   require(used()+sum(len(d['content'].encode('utf-8')) for d in batch)<=w['quota'],'Quota exceeded')
   for d in batch:docs[d['id']]={'deleted':False,'versions':[version(d['content'],1)]}
   return {'imported':len(batch)}
  id=data['id']
  if op=='document.put':
   require(role in ('admin','editor'),'Write permission required'); d=docs.get(id)
   require(not d or not d['deleted'],'Document deleted')
   n=len(d['versions']) if d else 0
   require(data['expected_revision']==n,'Revision conflict')
   v=version(data['content'],n+1); require(used()+v['size']<=w['quota'],'Quota exceeded')
   if d is None:d=docs[id]={'deleted':False,'versions':[]}
   d['versions'].append(v); return view(id,d)
  d=get_record(docs,id)
  if op=='document.get':
   require(not d['deleted'] or role=='admin','Document deleted')
   n=data.get('revision',len(d['versions'])); require(n<=len(d['versions']),'Missing revision')
   return view(id,d,n)
  if op=='document.delete':
   require(role in ('admin','editor'),'Write permission required'); require(not d['deleted'],'Already deleted')
   require(data['expected_revision']==len(d['versions']),'Revision conflict'); d['deleted']=True
   return view(id,d)
  admin(); require(d['deleted'],'Document must be deleted')
  if op=='document.restore':d['deleted']=False; return view(id,d)
  del docs[id]; return {'id':id,'purged':True}


if __name__=='__main__':Service.main()
