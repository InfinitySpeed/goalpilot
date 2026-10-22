import argparse,hashlib,json,os,re,sys
from pathlib import Path,PurePosixPath


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pairs(xs):
    d={}
    for k,v in xs:
        assert k not in d;d[k]=v
    return d

def load(state):
    if not state.exists():return {'version':1,'files':{}}
    x=json.loads(state.read_text(),object_pairs_hook=pairs)
    assert type(x['version']) is int and x['version']==1 and isinstance(x['files'],dict)
    for p,h in x['files'].items():
        assert p and '\\' not in p and ':' not in p and not p.startswith('/') and all(v not in ('','.','..') for v in p.split('/'))
        assert isinstance(h,str) and re.fullmatch('[a-f0-9]{64}',h)
    return x

def within(a,b):return a==b or b in a.parents

def main():
    p=argparse.ArgumentParser();p.add_argument('--state',required=True);s=p.add_subparsers(dest='cmd',required=True)
    q=s.add_parser('sync');q.add_argument('source');q.add_argument('dest');s.add_parser('status');a=p.parse_args()
    try:
        state=Path(a.state);old=load(state)
        if a.cmd=='status':print(json.dumps(old));return
        src,dst=Path(a.source),Path(a.dest)
        assert not src.is_symlink() and not dst.is_symlink() and src.is_dir()
        src,dst=src.resolve(),dst.resolve();st=state.resolve()
        assert not within(src,dst) and not within(dst,src) and not within(st,src) and not within(st,dst)
        source={}
        for root,dirs,files in os.walk(src,followlinks=False):
            dirs[:]=[d for d in dirs if not (Path(root)/d).is_symlink()]
            for name in files:
                f=Path(root)/name
                if not f.is_symlink() and f.is_file():source[f.relative_to(src).as_posix()]=sha(f)
        copies=[];deletes=[];same=[]
        for rel in sorted(set(source)|set(old['files'])):
            target=dst/rel
            assert not any(p.is_symlink() or (p.exists() and not p.is_dir()) for p in list(target.parents) if p!=dst and within(p,dst))
            assert not target.is_symlink() and (not target.exists() or target.is_file())
            current=sha(target) if target.exists() else None;new=source.get(rel);base=old['files'].get(rel)
            if current is not None:assert current==new or base is not None and current==base
            elif new is None:continue
            if new is None:deletes.append(rel)
            elif current==new:same.append(rel)
            else:copies.append(rel)
        for rel in copies:
            target=dst/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((src/rel).read_bytes())
        for rel in deletes:(dst/rel).unlink()
        state.parent.mkdir(parents=True,exist_ok=True)
        temp=state.with_name(state.name+'.tmp');temp.write_text(json.dumps({'version':1,'files':source}));os.replace(temp,state)
        print(json.dumps({'copied':copies,'deleted':deletes,'unchanged':same}))
    except Exception as e:print('Invalid operation: '+str(e),file=sys.stderr);sys.exit(2)


if __name__=='__main__':main()
