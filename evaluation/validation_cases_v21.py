"""Fresh validation projects, not used in the 0.2.0 campaign."""
import sys
import textwrap


def executable(code):
    return {'id':'behavior','description':'Independent user behavior',
            'command':[sys.executable,'-c',textwrap.dedent(code)],'timeout_seconds':30}


def cases():
    bookmarks={'name':'bookmarks','goal':"Transforme ce squelette en un gestionnaire de liens personnel fiable. Termine les parcours utiles et vérifie les erreurs sans perdre mes données.",
        'files':{
            'README.md':"""# Bookmarks
Implement the stdlib Python CLI: python bookmarks.py --store PATH add URL TITLE [--tags COMMA_LIST] | list [--tag TAG] | delete ID | export.
Store format: {"next_id":positive int,"items":[{"id":int,"url":str,"title":str,"tags":[str,...]},...]}.
New store starts next_id=1. IDs monotonically increase and are never reused after deletion.
URLs must be http/https with a nonempty hostname; URLs are unique by exact input string.
Title must not be blank. Tags: comma-separated, strip spaces, lowercase, discard blanks, deduplicate and sort.
add prints its item JSON. list and export print an array sorted by id. list --tag is an exact normalized tag filter.
delete prints the deleted item's JSON. Unknown ID -> exit 1. Invalid input, duplicate URL or malformed existing store -> exit 2, useful stderr, empty stdout and no store byte changes.
All existing rows and next_id must be validated before any operation: next_id > every id, unique positive int IDs/URLs, valid URL/title and normalized tags.
Unicode must round-trip. Create store parents as needed and use atomic file replacement for mutations.
No network requests, no external dependencies.
""",
            'bookmarks.py':"raise SystemExit('TODO: finish bookmark manager')\n",
            'storage.py':"def load(path):\n    return {'next_id': 1, 'items': []}\n"},
        'checks':[]}
    bookmarks['checks']=[executable(r'''
        import json,subprocess,sys,tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            store=Path(tmp)/'new'/'links.json'
            def call(*args,code=0):
                p=subprocess.run([sys.executable,'bookmarks.py','--store',str(store),*args],capture_output=True,text=True,timeout=5)
                assert p.returncode==code,(args,p.returncode,p.stderr)
                return json.loads(p.stdout) if p.stdout else None
            assert call('list')==[]
            first=call('add','https://example.org/a','Café 東京','--tags',' Work,work, été ,, ')
            assert first=={'id':1,'url':'https://example.org/a','title':'Café 東京','tags':['work','été']},first
            second=call('add','http://example.net','Other')
            assert second['id']==2 and second['tags']==[]
            assert call('list','--tag',' WORK ')==[first]
            assert call('delete','2')==second
            third=call('add','https://example.org/new','New','--tags','work')
            assert third['id']==3
            assert call('export')==[first,third]
            assert json.loads(store.read_text())['next_id']==4
    '''),executable(r'''
        import json,subprocess,sys,tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'links.json'
            def call(*args,code=0):
                p=subprocess.run([sys.executable,'bookmarks.py','--store',str(path),*args],capture_output=True,text=True,timeout=5)
                assert p.returncode==code,(args,p.returncode,p.stderr)
                if code:assert p.stderr and not p.stdout
            call('add','https://example.org','One')
            before=path.read_bytes()
            for args in [('add','ftp://x','Bad'),('add','https:///missing','Bad'),('add','https://x','  '),('add','https://example.org','Duplicate')]:
                call(*args,code=2);assert path.read_bytes()==before
            call('delete','99',code=1);assert path.read_bytes()==before
            valid=json.loads(before)
            for bad in [b'{bad',json.dumps({'next_id':1,'items':valid['items']}).encode(),json.dumps({'next_id':2,'items':[dict(valid['items'][0],id=True)]}).encode()]:
                path.write_bytes(bad)
                call('list',code=2);assert path.read_bytes()==bad
    ''')]
    for i,c in enumerate(bookmarks['checks']):c['id']=f'bookmarks-{i+1}'

    bundle={'name':'bundle','goal':"Finis cet outil pour sauvegarder et restaurer un dossier de travail local de façon fiable, avec des contrôles utiles.",
        'files':{
            'README.md':"""# Local bundle
Implement stdlib CLI: python bundle.py pack SOURCE ARCHIVE | list ARCHIVE | unpack ARCHIVE DEST.
pack archives every regular file recursively with POSIX relative paths; include dotfiles, exclude symlinks and empty directories. Output JSON array of archived paths sorted lexicographically. Create archive parent directories as needed.
list outputs the same sorted file-path array; unpack extracts all files and prints that array.
Reject archives containing any absolute path, '..' segment, backslash, Windows drive prefix, duplicate file member, or symlink member. Validate ALL names before any destination changes, including directory entries. Reject extraction if an existing path component or target is a symlink, if any target file already exists, or if an existing parent is a regular file. All validation precedes all writes. No overwrite option.
For valid archives unpack creates missing destination directories, restores nested file bytes and Unicode paths.
Missing/bad source/archive, unsafe archive or conflicting destination: exit 2, useful stderr, empty stdout. No destination data changes on these validation errors. Existing archive bytes must remain unchanged when pack has an invalid source.
Archive must be outside SOURCE; reject pack into SOURCE, including an existing archive there, before writing. No dependencies and no network.
""",
            'bundle.py':"raise SystemExit('TODO: finish bundle CLI')\n",
            'paths.py':"def safe(name):\n    return bool(name)\n"},
        'checks':[]}
    bundle['checks']=[executable(r'''
        import json,subprocess,sys,tempfile,os
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'source';src.mkdir();(src/'nested').mkdir()
            expected={'.config':b'yes','nested/été 東京.txt':'café'.encode(), 'zero.bin':b'\0\1\2'}
            for name,data in expected.items():(src/name).write_bytes(data)
            (src/'empty').mkdir();(src/'link').symlink_to(src/'zero.bin')
            archive=root/'backup'/'save.zip';dest=root/'restored'
            def call(*args):
                p=subprocess.run([sys.executable,'bundle.py',*map(str,args)],capture_output=True,text=True,timeout=5)
                assert p.returncode==0,(args,p.stderr)
                assert json.loads(p.stdout)==sorted(expected),p.stdout
            call('pack',src,archive);call('list',archive);call('unpack',archive,dest)
            assert {p.relative_to(dest).as_posix():p.read_bytes() for p in dest.rglob('*') if p.is_file()}==expected
    '''),executable(r'''
        import json,subprocess,sys,tempfile,zipfile,stat
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'bad.zip';dest=root/'dest';dest.mkdir();(dest/'keep').write_bytes(b'unchanged')
            def reject(*args):
                p=subprocess.run([sys.executable,'bundle.py',*map(str,args)],capture_output=True,text=True,timeout=5)
                assert p.returncode==2,(args,p.returncode,p.stderr)
                assert p.stderr and not p.stdout
            def snapshot():return {p.relative_to(dest).as_posix():p.read_bytes() for p in dest.rglob('*') if p.is_file()}
            for name in ['../escape','/absolute','safe/../escape','C:/escape','back\\slash']:
                with zipfile.ZipFile(archive,'w') as z:z.writestr('first.txt','not committed');z.writestr(name,'bad')
                reject('unpack',archive,dest);assert snapshot()=={'keep':b'unchanged'}
                assert not (root/'escape').exists()
            with zipfile.ZipFile(archive,'w') as z:
                info=zipfile.ZipInfo('sym');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,'target')
            reject('unpack',archive,dest)
            with zipfile.ZipFile(archive,'w') as z:z.writestr('new','no');z.writestr('keep','replace')
            reject('unpack',archive,dest);assert snapshot()=={'keep':b'unchanged'}
            external=root/'external';external.mkdir();(dest/'link').symlink_to(external,target_is_directory=True)
            with zipfile.ZipFile(archive,'w') as z:z.writestr('new','no');z.writestr('link/write','bad')
            reject('unpack',archive,dest);assert not list(external.iterdir()) and not (dest/'new').exists()
            before=archive.read_bytes();reject('pack',root/'missing',archive);assert archive.read_bytes()==before
            reject('pack',dest,dest/'recursive.zip');assert not (dest/'recursive.zip').exists()
    ''')]
    for i,c in enumerate(bundle['checks']):c['id']=f'bundle-{i+1}'

    tasks={'name':'tasks','goal':"Rends ce gestionnaire de tâches utilisable pour mener un projet à son terme, avec dépendances et conservation fiable de mon travail.",
        'files':{
            'README.md':"""# Task dependencies
Implement stdlib CLI python tasks.py --store PATH add TITLE [--after comma-separated-IDs] | list | ready | done ID | delete ID | export.
Store JSON: {"next_id":positive int,"tasks":[{"id":positive int,"title":nonblank str,"after":[sorted unique positive IDs],"done":bool},...]}.
New empty store starts next_id=1. IDs never reused. add prints new task. Only existing dependencies may be named, including completed ones. Normalize whitespace in --after, deduplicate/sort IDs; malformed/nonpositive/unknown ID -> exit 2. No dependencies by default.
list/export print task arrays sorted by id. ready prints unfinished tasks all of whose dependencies are done, sorted by id.
done ID prints updated task and is idempotent, but fails exit 2 if unfinished dependencies exist. Unknown target done/delete -> exit 1.
delete prints removed task; fail exit 2 if any other task depends on it, even when done.
Reject malformed existing store or inconsistent types, duplicate IDs, invalid next_id, missing/self dependencies and dependency cycles with exit 2 before any operation.
Invalid input -> useful stderr and no stdout; every failed mutation leaves original store bytes unchanged.
Unicode must round-trip, create store parent dirs as needed, mutations use atomic replacement. No dependencies or network.
""",
            'tasks.py':"raise SystemExit('TODO: finish task dependencies')\n",
            'graph.py':"def ready(tasks):\n    return tasks\n"},
        'checks':[]}
    tasks['checks']=[executable(r'''
        import json,subprocess,sys,tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'nested'/'tasks.json'
            def call(*args,code=0):
                p=subprocess.run([sys.executable,'tasks.py','--store',str(path),*args],capture_output=True,text=True,timeout=5)
                assert p.returncode==code,(args,p.returncode,p.stderr)
                return json.loads(p.stdout) if p.stdout else None
            assert call('ready')==[]
            a=call('add','Préparer 東京');b=call('add','Build','--after',' 1,1 ');c=call('add','Ship','--after','2,1')
            assert a=={'id':1,'title':'Préparer 東京','after':[],'done':False}
            assert b['after']==[1] and c['after']==[1,2]
            assert call('ready')==[a]
            before=path.read_bytes();call('done','2',code=2);assert path.read_bytes()==before
            a=call('done','1');assert a['done'] is True
            assert call('done','1')==a
            assert call('ready')==[b]
            b=call('done','2');assert call('ready')==[c]
            c=call('done','3');assert call('ready')==[]
            before=path.read_bytes();call('delete','1',code=2);assert path.read_bytes()==before
            assert call('delete','3')==c
            assert call('add','Next')['id']==4
            assert [x['id'] for x in call('export')]==[1,2,4]
    '''),executable(r'''
        import json,subprocess,sys,tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'tasks.json'
            def call(*args,code=0):
                p=subprocess.run([sys.executable,'tasks.py','--store',str(path),*args],capture_output=True,text=True,timeout=5)
                assert p.returncode==code,(args,p.returncode,p.stderr)
                if code:assert p.stderr and not p.stdout
            call('add','First');before=path.read_bytes()
            for args in [('add','  '),('add','Bad','--after','99'),('add','Bad','--after','1.0'),('add','Bad','--after','0')]:
                call(*args,code=2);assert path.read_bytes()==before
            call('done','999',code=1);call('delete','999',code=1);assert path.read_bytes()==before
            a={'id':1,'title':'A','after':[2],'done':False};b={'id':2,'title':'B','after':[1],'done':False}
            for store in [
                {'next_id':3,'tasks':[a,b]},
                {'next_id':2,'tasks':[dict(a,after=[1])]},
                {'next_id':2,'tasks':[dict(a,after=[99])]},
                {'next_id':1,'tasks':[dict(a,after=[])]},
                {'next_id':2,'tasks':[dict(a,id=True,after=[])]},
                {'next_id':2,'tasks':[dict(a,done=1,after=[])]}]:
                path.write_text(json.dumps(store));bad=path.read_bytes()
                call('list',code=2);assert path.read_bytes()==bad
    ''')]
    for i,c in enumerate(tasks['checks']):c['id']=f'tasks-{i+1}'
    return [bookmarks,bundle,tasks]
