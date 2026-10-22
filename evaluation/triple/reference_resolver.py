import re
from functools import cmp_to_key


class ResolutionError(ValueError):pass


def version(s):
    if not isinstance(s,str):raise ValueError('version')
    m=re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?',s)
    if not m:raise ValueError('version')
    core=tuple(map(int,m.group(1,2,3)));pre=m.group(4)
    parts=pre.split('.')if pre else []
    if any(x.isdigit()and len(x)>1 and x.startswith('0')for x in parts):raise ValueError('prerelease')
    return core,tuple((0,int(x))if x.isdigit()else(1,x)for x in parts),pre is None

def precedence(s):
    core,pre,stable=version(s);return (*core,stable,pre)

def compare_versions(a,b):
    x,y=precedence(a),precedence(b);return (x>y)-(x<y)

def branches(text):
    if not isinstance(text,str)or not text.strip():raise ValueError('range')
    result=[]
    for branch in text.split('||'):
        if not branch.strip():raise ValueError('empty branch')
        conditions=[];pres=set()
        for token in branch.split():
            if token=='*':continue
            wild=re.fullmatch(r'(0|[1-9][0-9]*)(?:\.(0|[1-9][0-9]*))?\.\*',token)
            if wild:
                major=int(wild[1]);minor=int(wild[2]or 0)
                low=f'{major}.{minor}.0';high=f'{major+1}.0.0'if wild[2]is None else f'{major}.{minor+1}.0'
                conditions += [('>=',low),('<',high)];continue
            if token.startswith(('^','~')):
                base=token[1:];core,pre,stable=version(base)
                if not stable:pres.add(core)
                a,b,c=core
                if token[0]=='~':upper=f'{a}.{b+1}.0'
                elif a:upper=f'{a+1}.0.0'
                elif b:upper=f'0.{b+1}.0'
                else:upper=f'0.0.{c+1}'
                conditions += [('>=',base),('<',upper)];continue
            match=re.fullmatch(r'(>=|<=|>|<|=)?(.+)',token)
            if not match:raise ValueError('comparator')
            op,base=match[1]or '=',match[2];core,pre,stable=version(base)
            if not stable:pres.add(core)
            conditions.append((op,base))
        result.append((conditions,pres))
    return result

def satisfies(v,text,allow_prerelease=False):
    if type(allow_prerelease)is not bool:raise ValueError('flag')
    core,_,stable=version(v);parts=branches(text)
    def check(op,base):
        c=compare_versions(v,base)
        return {'=':c==0,'>':c>0,'<':c<0,'>=':c>=0,'<=':c<=0}[op]
    return any((stable or allow_prerelease or core in pres)and all(check(op,base)for op,base in conditions)for conditions,pres in parts)

def name(s):
    if not isinstance(s,str)or not re.fullmatch('[a-z][a-z0-9_-]*',s):raise ValueError('name')

def resolve(catalog,requests,locked=None,allow_prerelease=False):
    if type(allow_prerelease)is not bool or not isinstance(catalog,dict)or not isinstance(requests,dict):raise ValueError('schema')
    for package,releases in catalog.items():
        name(package)
        if not isinstance(releases,list):raise ValueError('releases')
        seen=set()
        for release in releases:
            if not isinstance(release,dict)or set(release)-{'version','dependencies','yanked'}or not {'version','dependencies'}<=set(release):raise ValueError('release')
            version(release['version'])
            if release['version']in seen:raise ValueError('duplicate')
            seen.add(release['version'])
            if type(release.get('yanked',False))is not bool or not isinstance(release['dependencies'],dict):raise ValueError('metadata')
            for dep,constraint in release['dependencies'].items():name(dep);branches(constraint)
    for package,constraint in requests.items():name(package);branches(constraint)
    if locked is None:locked={}
    if not isinstance(locked,dict):raise ValueError('locked')
    for package,v in locked.items():name(package);version(v)
    def valid(v,constraints):return all(satisfies(v,c,allow_prerelease)for c in constraints)
    def search(chosen,constraints):
        if any(not valid(v,constraints[k])for k,v in chosen.items()):return None
        pending=sorted(set(constraints)-set(chosen))
        if not pending:return chosen
        package=pending[0]
        candidates=[r for r in catalog.get(package,[])if not r.get('yanked',False)and valid(r['version'],constraints[package])]
        def compare(a,b):
            al,bl=a['version']==locked.get(package),b['version']==locked.get(package)
            if al!=bl:return -1 if al else 1
            return -compare_versions(a['version'],b['version'])or ((a['version']>b['version'])-(a['version']<b['version']))
        candidates.sort(key=cmp_to_key(compare))
        for release in candidates:
            next_constraints={k:list(v)for k,v in constraints.items()}
            for dep,c in release['dependencies'].items():next_constraints.setdefault(dep,[]).append(c)
            answer=search({**chosen,package:release['version']},next_constraints)
            if answer is not None:return answer
        return None
    out=search({}, {k:[v]for k,v in requests.items()})
    if out is None:raise ResolutionError('No compatible complete graph')
    return dict(sorted(out.items()))
