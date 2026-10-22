"""Independent attainable-reference preflight. Never sent to coding agents."""
from pathlib import Path
import tempfile
import time
from goalpilot.engine import verify
from .validation_cases_v21 import cases


BOOKMARKS=r'''
import argparse,json,os,sys,tempfile
from pathlib import Path
from urllib.parse import urlsplit
def url(s):
    try:return isinstance(s,str) and urlsplit(s).scheme in ('http','https') and bool(urlsplit(s).hostname)
    except ValueError:return False
def tags(s):return sorted(set(x.strip().lower() for x in s.split(',') if x.strip()))
def positive(n):return type(n) is int and n>0
def main():
    p=argparse.ArgumentParser();p.add_argument('--store',required=True);s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('add');a.add_argument('url');a.add_argument('title');a.add_argument('--tags',default='')
    a=s.add_parser('list');a.add_argument('--tag');s.add_parser('export')
    a=s.add_parser('delete');a.add_argument('id',type=int)
    a=p.parse_args();path=Path(a.store)
    data=json.loads(path.read_text()) if path.exists() else {'next_id':1,'items':[]}
    assert isinstance(data,dict) and positive(data['next_id']) and isinstance(data['items'],list)
    ids=set();urls=set()
    for x in data['items']:
        assert isinstance(x,dict) and positive(x['id']) and x['id']<data['next_id'] and x['id'] not in ids
        assert url(x['url']) and x['url'] not in urls and isinstance(x['title'],str) and x['title'].strip()
        assert isinstance(x['tags'],list) and all(isinstance(t,str) and t and t==t.strip().lower() for t in x['tags']) and x['tags']==sorted(set(x['tags']))
        ids.add(x['id']);urls.add(x['url'])
    rows=data['items'];changed=False
    if a.cmd=='add':
        assert url(a.url) and a.url not in urls and a.title.strip()
        result={'id':data['next_id'],'url':a.url,'title':a.title,'tags':tags(a.tags)}
        rows.append(result);data['next_id']+=1;changed=True
    elif a.cmd=='delete':
        result=next((x for x in rows if x['id']==a.id),None)
        if result is None:print('Unknown ID',file=sys.stderr);return 1
        rows.remove(result);changed=True
    else:result=sorted([x for x in rows if a.cmd!='list' or a.tag is None or a.tag.strip().lower() in x['tags']],key=lambda x:x['id'])
    if changed:
        path.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(dir=path.parent)
        with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False)
        os.replace(tmp,path)
    print(json.dumps(result,ensure_ascii=False));return 0
try:sys.exit(main())
except (ValueError,KeyError,TypeError,AssertionError,OSError):print('Invalid input or store',file=sys.stderr);sys.exit(2)
'''

TASKS=r'''
import argparse,json,os,sys,tempfile
from pathlib import Path
def pos(x):return type(x) is int and x>0
def main():
    p=argparse.ArgumentParser();p.add_argument('--store',required=True);s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('add');a.add_argument('title');a.add_argument('--after',default='')
    for name in ('list','ready','export'):s.add_parser(name)
    for name in ('done','delete'):s.add_parser(name).add_argument('id',type=int)
    a=p.parse_args();path=Path(a.store);data=json.loads(path.read_text()) if path.exists() else {'next_id':1,'tasks':[]}
    assert isinstance(data,dict) and pos(data['next_id']) and isinstance(data['tasks'],list)
    rows=data['tasks'];index={}
    for x in rows:
        assert isinstance(x,dict) and pos(x['id']) and x['id']<data['next_id'] and x['id'] not in index
        assert isinstance(x['title'],str) and x['title'].strip() and type(x['done']) is bool
        assert isinstance(x['after'],list) and all(pos(i) for i in x['after']) and x['after']==sorted(set(x['after']))
        index[x['id']]=x
    seen=set();stack=set()
    def visit(i):
        assert i in index and i not in stack
        if i in seen:return
        stack.add(i)
        for j in index[i]['after']:visit(j)
        stack.remove(i);seen.add(i)
    for i in index:visit(i)
    changed=False
    if a.cmd=='add':
        assert a.title.strip()
        raw=a.after.split(',') if a.after else []
        assert all(x.strip().isascii() and x.strip().isdigit() for x in raw)
        after=sorted(set(map(int,raw)));assert all(pos(i) and i in index for i in after)
        result={'id':data['next_id'],'title':a.title,'after':after,'done':False}
        rows.append(result);data['next_id']+=1;changed=True
    elif a.cmd in ('done','delete'):
        if a.id not in index:print('Unknown ID',file=sys.stderr);return 1
        result=index[a.id]
        if a.cmd=='done':
            assert all(index[i]['done'] for i in result['after'])
            result['done']=True
        else:
            assert not any(a.id in x['after'] for x in rows)
            rows.remove(result)
        changed=True
    else:result=sorted([x for x in rows if a.cmd!='ready' or not x['done'] and all(index[i]['done'] for i in x['after'])],key=lambda x:x['id'])
    if changed:
        path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(dir=path.parent)
        with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False)
        os.replace(tmp,path)
    print(json.dumps(result,ensure_ascii=False));return 0
try:sys.exit(main())
except (ValueError,KeyError,TypeError,AssertionError,OSError):print('Invalid input or store',file=sys.stderr);sys.exit(2)
'''

BUNDLE=r'''
import argparse,json,os,re,stat,sys,tempfile,zipfile
from pathlib import Path,PurePosixPath
def entries(z):
    result={};dirs=[]
    for info in z.infolist():
        name=info.filename
        assert name and not name.startswith('/') and '\\' not in name and '..' not in name.split('/') and not re.match(r'^[a-zA-Z]:',name)
        assert stat.S_IFMT(info.external_attr>>16)!=stat.S_IFLNK
        if info.is_dir():dirs.append(name);continue
        assert name not in result
        result[name]=z.read(info)
    return result,dirs
def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('pack');a.add_argument('source');a.add_argument('archive')
    a=s.add_parser('list');a.add_argument('archive')
    a=s.add_parser('unpack');a.add_argument('archive');a.add_argument('dest')
    a=p.parse_args();archive=Path(a.archive)
    if a.cmd=='pack':
        source=Path(a.source).resolve();assert source.is_dir()
        assert archive.resolve()!=source and source not in archive.resolve().parents
        files=[]
        for base,dirs,names in os.walk(source,followlinks=False):
            dirs[:]=[d for d in dirs if not (Path(base)/d).is_symlink()]
            files.extend(Path(base)/n for n in names if not (Path(base)/n).is_symlink() and (Path(base)/n).is_file())
        files.sort(key=lambda x:x.relative_to(source).as_posix())
        archive.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(dir=archive.parent);os.close(fd)
        try:
            with zipfile.ZipFile(tmp,'w') as z:
                for f in files:z.write(f,f.relative_to(source).as_posix())
            os.replace(tmp,archive)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        result=[f.relative_to(source).as_posix() for f in files]
    else:
        with zipfile.ZipFile(archive) as z:files,dirs=entries(z)
        result=sorted(files)
        if a.cmd=='unpack':
            dest=Path(a.dest).absolute()
            for name in list(files)+dirs:
                target=dest/Path(*PurePosixPath(name).parts)
                for parent in [dest,*target.parents]:
                    assert not parent.is_symlink() and (not parent.exists() or parent.is_dir())
                assert not target.is_symlink()
                if name in files:assert not target.exists()
                else:assert not target.exists() or target.is_dir()
            for name in dirs:(dest/name).mkdir(parents=True,exist_ok=True)
            for name,data in files.items():
                target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    print(json.dumps(result,ensure_ascii=False))
try:main()
except (ValueError,KeyError,TypeError,AssertionError,OSError,zipfile.BadZipFile):print('Invalid source/archive/destination',file=sys.stderr);sys.exit(2)
'''

def preflight():
    result=[]
    references={'bookmarks':('bookmarks.py',BOOKMARKS),'bundle':('bundle.py',BUNDLE),'tasks':('tasks.py',TASKS)}
    for case in cases():
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);repo=root/'repo';repo.mkdir()
            for name,source in case['files'].items():(repo/name).write_text(source)
            unfinished=verify({'repo':str(repo),'checks':case['checks']},time.monotonic()+60,root/'before')
            assert not any(x['passed'] for x in unfinished)
            name,reference=references[case['name']]
            (repo/name).write_text(reference)
            completed=verify({'repo':str(repo),'checks':case['checks']},time.monotonic()+60,root/'after')
            assert all(x['passed'] for x in completed),[(x['id'],x['output']) for x in completed]
            result.append({'case':case['name'],'unfinished_seed_rejected':True,'reference_checks_passed':len(completed)})
    return {'kind':'independent_verifier_preflight','live_model_calls':0,'cases':result}


if __name__=='__main__':
    import json
    print(json.dumps(preflight(),indent=2))
