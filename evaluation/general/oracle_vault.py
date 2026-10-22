"""Independent content-addressed backup reference, never given to live agents."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile


def validpath(s):
    return isinstance(s,str) and bool(s) and not s.startswith('/') and '\\' not in s and not re.match(r'^[A-Za-z]:',s) and all(x not in ('','..','.') for x in s.split('/'))
def pos(x):return type(x) is int and x>0
def load(root):
    path=root/'manifest.json'
    m=json.loads(path.read_text()) if path.exists() else {'version':2,'next_id':1,'snapshots':[]}
    assert isinstance(m,dict) and type(m['version']) is int and m['version'] in (1,2) and isinstance(m['snapshots'],list)
    ids=set()
    for s in m['snapshots']:
        assert isinstance(s,dict) and pos(s['id']) and s['id'] not in ids and isinstance(s['label'],str) and isinstance(s['files'],list)
        ids.add(s['id']);paths=set()
        for f in s['files']:
            assert isinstance(f,dict) and validpath(f['path']) and f['path'] not in paths
            assert type(f['size']) is int and f['size']>=0 and isinstance(f['sha256'],str) and re.fullmatch('[a-f0-9]{64}',f['sha256'])
            paths.add(f['path'])
    if m['version']==1:m['version']=2;m['next_id']=max(ids,default=0)+1
    assert pos(m['next_id']) and m['next_id']>max(ids,default=0)
    return m
def atom(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(data)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def save(root,m):atom(root/'manifest.json',json.dumps(m,ensure_ascii=False).encode())
def inspect(root,s):
    missing=[];corrupt=[];content={}
    for f in s['files']:
        p=root/'objects'/f['sha256']
        if not p.is_file() or p.is_symlink():missing.append(f['path']);continue
        raw=p.read_bytes()
        if len(raw)!=f['size'] or hashlib.sha256(raw).hexdigest()!=f['sha256']:corrupt.append(f['path'])
        else:content[f['path']]=raw
    return {'id':s['id'],'ok':not missing and not corrupt,'missing':sorted(missing),'corrupt':sorted(corrupt)},content
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('snapshot');a.add_argument('source');a.add_argument('--label',default='')
    s.add_parser('list')
    a=s.add_parser('verify');a.add_argument('id',type=int)
    a=s.add_parser('restore');a.add_argument('id',type=int);a.add_argument('dest')
    a=s.add_parser('prune');a.add_argument('--keep',type=int,required=True)
    a=p.parse_args();root=Path(a.root).resolve();m=load(root);code=0
    if a.cmd=='list':value=[{'id':s['id'],'label':s['label'],'files':len(s['files'])} for s in sorted(m['snapshots'],key=lambda s:s['id'])]
    elif a.cmd=='snapshot':
        source=Path(a.source).resolve();assert source.is_dir() and root!=source and root not in source.parents and source not in root.parents
        entries=[];objects={}
        for directory,dirs,files in os.walk(source,followlinks=False):
            dirs[:]=[x for x in dirs if not (Path(directory)/x).is_symlink()]
            for name in files:
                path=Path(directory)/name
                if path.is_symlink() or not path.is_file():continue
                raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest();rel=path.relative_to(source).as_posix();assert validpath(rel)
                entries.append({'path':rel,'size':len(raw),'sha256':sha});objects[sha]=raw
        for sha,raw in objects.items():
            path=root/'objects'/sha
            if path.exists():assert not path.is_symlink() and path.is_file() and path.read_bytes()==raw
        added=0
        for sha,raw in objects.items():
            path=root/'objects'/sha
            if not path.exists():atom(path,raw);added+=1
        ident=m['next_id'];m['next_id']+=1;m['snapshots'].append({'id':ident,'label':a.label,'files':sorted(entries,key=lambda x:x['path'])});save(root,m)
        value={'id':ident,'label':a.label,'files':len(entries),'added_objects':added}
    elif a.cmd in ('verify','restore'):
        found=next((x for x in m['snapshots'] if x['id']==a.id),None);assert found is not None
        info,content=inspect(root,found)
        if a.cmd=='verify':value=info;code=0 if info['ok'] else 1
        else:
            assert info['ok'];dest=Path(a.dest).absolute()
            for name in content:
                target=dest/name
                assert not target.exists() and not target.is_symlink()
                for parent in [dest,*target.parents]:assert not parent.is_symlink() and (not parent.exists() or parent.is_dir())
            for name,raw in content.items():
                target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
            value={'id':a.id,'files':len(content)}
    else:
        assert a.keep>=0;ordered=sorted(m['snapshots'],key=lambda x:x['id']);keep=ordered[-a.keep:] if a.keep else []
        removed=[x['id'] for x in ordered if x not in keep];m['snapshots']=keep;live={f['sha256'] for s in keep for f in s['files']};save(root,m);count=0
        if (root/'objects').exists():
            for path in (root/'objects').iterdir():
                if re.fullmatch('[a-f0-9]{64}',path.name) and path.name not in live and path.is_file() and not path.is_symlink():path.unlink();count+=1
        value={'removed_snapshots':removed,'removed_objects':count}
    print(json.dumps(value,ensure_ascii=False));return code


if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,AssertionError,KeyError,TypeError,OSError) as e:print(str(e) or 'invalid input/archive/destination',file=sys.stderr);sys.exit(2)
