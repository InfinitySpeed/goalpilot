"""Previously unused multi-file projects with frozen independent acceptance."""

from goalpilot.benchmark import check


INVENTORY_README = '''# Inventaire local à terminer
Bibliothèque standard Python uniquement. Entrée : python inventory.py --store PATH COMMANDE.
Stockage : tableau JSON {sku: chaîne non vide, name: chaîne non vide, quantity: entier >= 0}.
Commandes : add SKU NAME QTY ; adjust SKU DELTA ; list ; import CSV_PATH ; export.
add refuse un SKU déjà présent. adjust refuse un SKU absent ou un résultat négatif.
list et export émettent un tableau JSON trié par SKU. Données Unicode préservées.
CSV : en-têtes sku,name,quantity dans n'importe quel ordre, tous obligatoires ; noms entre guillemets possibles.
import ajoute les lignes aux données existantes, refuse les doublons internes/externes et valide toutes les
lignes avant de modifier le stockage. En cas d'erreur (entrée, stockage malformé, quantité invalide),
sortie 2 et données existantes inchangées. Toute opération réussie retourne 0.
Un stockage absent est vide. Documenter l'utilisation. Aucun service externe ni dépendance.
'''

AGENDA_README = '''# Agenda de salles à terminer
Bibliothèque standard Python uniquement. Entrée : python agenda.py --db PATH COMMANDE.
Commandes : add ROOM START END TITLE ; list [--room ROOM] ; delete ID ; export.
Dates UTC sans suffixe : exactement YYYY-MM-DDTHH:MM, dates calendaires réelles, START < END.
ROOM et TITLE sont des chaînes non blanches ; conserver leur texte Unicode et les apostrophes.
Les réservations d'une même salle ne peuvent pas se chevaucher ; les intervalles sont [start,end),
donc des réservations adjacentes sont autorisées. Des salles différentes peuvent partager un créneau.
Stockage SQLite persistant. IDs entiers strictement croissants, non réutilisés après suppression.
list et export émettent un tableau JSON {id,room,start,end,title}, trié par start puis id.
list --room filtre une salle. export retourne toutes les lignes. delete absent retourne 1 sans modification.
Entrées invalides ou conflit : code 2 et aucune modification. Succès : code 0. Documenter l'utilisation.
'''

PIPELINE_README = '''# Importeur de transactions JSONL à terminer
Bibliothèque standard Python uniquement. Entrée : python pipeline.py INPUT --output OUTPUT [--strict].
Chaque ligne non blanche est un objet {id,user,currency,amount}. id et user : chaînes non blanches ;
currency : trois lettres ASCII majuscules ; amount : chaîne décimale signée, finie, sans exposant,
au plus deux décimales. Les autres champs sont ignorés. Les lignes blanches sont ignorées.
Valider avant de dédupliquer : le premier enregistrement valide d'un ID est conservé, les suivants
valides sont des doublons. Une ligne malformée reste invalide même si son ID est un doublon.
Rapport JSON : {records: entier, totals: {devise: chaîne à deux décimales}, users: chaînes uniques triées,
invalid_rows: entier, duplicate_rows: entier}. Totaux décimaux exacts, avoirs négatifs autorisés.
Sans --strict, ignorer et compter les lignes invalides ; avec --strict, une ligne invalide fait échouer
tout le traitement avec code 2, stderr explicite, aucun stdout et ancien OUTPUT inchangé octet pour octet.
Succès : code 0, écrire atomiquement OUTPUT et émettre le même rapport JSON sur stdout.
Un fichier vide donne un rapport vide valide. Préserver Unicode. Documenter l'utilisation.
'''


def cases():
    inventory = [
        check('inventory-workflow','Persistent add, adjust, sorted export, Unicode and CSV import','inventory.py',r'''
        import csv
        with tempfile.TemporaryDirectory() as d:
            store=Path(d)/'stock.json'
            for sku,name,qty in [('z9','Café, thé',7),('a1','旅の記録',4)]:
                p=call('--store',store,'add',sku,name,qty)
                assert p.returncode==0,p.stderr
            assert call('--store',store,'adjust','z9',-3).returncode==0
            source=Path(d)/'stock.csv'
            with source.open('w',newline='') as stream:
                writer=csv.writer(stream);writer.writerow(['quantity','sku','name'])
                for i in range(20):writer.writerow([i,f'b{i:02d}',f'Article {i}, été'])
            p=call('--store',store,'import',source)
            assert p.returncode==0,p.stderr
            p=call('--store',store,'export')
            assert p.returncode==0,p.stderr
            rows=json.loads(p.stdout)
            assert len(rows)==22 and [x['sku'] for x in rows]==sorted(x['sku'] for x in rows),rows
            assert all(type(x['quantity']) is int for x in rows),rows
            by={x['sku']:x for x in rows}
            assert by['z9']=={'sku':'z9','name':'Café, thé','quantity':4},by
            assert by['a1']['name']=='旅の記録'
            assert all(by[f'b{i:02d}']['quantity']==i for i in range(20))
            p=call('--store',store,'list')
            assert p.returncode==0 and json.loads(p.stdout)==rows,p.stdout+p.stderr
        '''),
        check('inventory-atomic-errors','Invalid changes and partial CSV imports preserve all existing bytes','inventory.py',r'''
        with tempfile.TemporaryDirectory() as d:
            store=Path(d)/'stock.json'
            original=[{'sku':'existing','name':'Original','quantity':3}]
            store.write_text(json.dumps(original));before=store.read_bytes()
            for args in [('add','existing','Duplicate',9),('adjust','existing',-4),('adjust','missing',2),('add','bad','Name','1.5')]:
                p=call('--store',store,*args)
                assert p.returncode==2,(args,p.returncode,p.stderr)
                assert store.read_bytes()==before,args
            source=Path(d)/'bad.csv'
            for rows in ['sku,name,quantity\nnew,Good,2\nbroken,Bad,nope\n','sku,name,quantity\nnew,One,2\nnew,Two,3\n','sku,name,quantity\nnew,Good,2\nexisting,Duplicate,4\n']:
                source.write_text(rows)
                p=call('--store',store,'import',source)
                assert p.returncode==2,(p.returncode,p.stderr)
                assert store.read_bytes()==before
            store.write_text('{"not":"an array"}')
            before=store.read_bytes()
            p=call('--store',store,'add','new','Name',2)
            assert p.returncode==2 and store.read_bytes()==before,(p.returncode,p.stderr)
        '''),
    ]
    agenda = [
        check('agenda-workflow','Persistent bookings, adjacent intervals, room filters and Unicode','agenda.py',r'''
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'agenda.sqlite'
            requests=[('A','2026-05-10T09:00','2026-05-10T10:00',"Réunion d'équipe"),('A','2026-05-10T10:00','2026-05-10T11:00','Suivi'),('B','2026-05-10T09:30','2026-05-10T10:30','計画')]
            for request in requests:
                p=call('--db',db,'add',*request);assert p.returncode==0,p.stderr
            p=call('--db',db,'list');assert p.returncode==0,p.stderr
            rows=json.loads(p.stdout)
            assert len(rows)==3 and [x['id'] for x in rows]==[1,3,2],rows
            assert rows[0]['title']=="Réunion d'équipe" and rows[1]['title']=='計画'
            assert rows[0]['start']=='2026-05-10T09:00' and rows[0]['end']=='2026-05-10T10:00'
            p=call('--db',db,'list','--room','A')
            assert p.returncode==0 and [x['id'] for x in json.loads(p.stdout)]==[1,2],p.stdout+p.stderr
            p=call('--db',db,'export')
            assert p.returncode==0 and json.loads(p.stdout)==rows,p.stdout+p.stderr
        '''),
        check('agenda-conflicts','Reject overlapping/invalid reservations without modifying accepted rows','agenda.py',r'''
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'agenda.sqlite'
            p=call('--db',db,'add','A','2026-06-01T08:00','2026-06-01T09:00','Keep')
            assert p.returncode==0,p.stderr
            for room,start,end,title in [('A','2026-06-01T08:30','2026-06-01T09:30','Overlap'),('A','2026-06-01T07:00','2026-06-01T10:00','Contains'),('A','2026-06-01T08:00','2026-06-01T08:00','Empty'),('A','2026-04-31T08:00','2026-05-01T08:00','Bad date'),(' ','2026-06-01T10:00','2026-06-01T11:00','Bad room')]:
                p=call('--db',db,'add',room,start,end,title)
                assert p.returncode==2,(room,start,end,p.returncode,p.stderr)
                rows=json.loads(call('--db',db,'list').stdout)
                assert len(rows)==1 and rows[0]['title']=='Keep',rows
        '''),
        check('agenda-delete','Deleted IDs are not reused; absent delete leaves data untouched','agenda.py',r'''
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'agenda.sqlite'
            for hour in (9,11):
                assert call('--db',db,'add','A',f'2026-06-02T{hour:02d}:00',f'2026-06-02T{hour+1:02d}:00','Event').returncode==0
            before=json.loads(call('--db',db,'export').stdout)
            p=call('--db',db,'delete',999)
            assert p.returncode==1,p.returncode
            assert json.loads(call('--db',db,'export').stdout)==before
            assert call('--db',db,'delete',2).returncode==0
            assert call('--db',db,'add','A','2026-06-02T13:00','2026-06-02T14:00','New').returncode==0
            rows=json.loads(call('--db',db,'list').stdout)
            assert [x['id'] for x in rows]==[1,3],rows
        '''),
    ]
    pipeline = [
        check('pipeline-summary','Exact totals, Unicode, deduplication and malformed-row accounting','pipeline.py',r'''
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'input.jsonl';output=Path(d)/'report.json'
            rows=[{'id':'x1','user':'Élodie','currency':'EUR','amount':'0.10'},{'id':'x2','user':'李','currency':'EUR','amount':'0.20'},{'id':'x1','user':'Élodie','currency':'EUR','amount':'0.10'},'invalid-json',{'id':'bad','user':'A','currency':'EUR','amount':'NaN'},{'id':'x3','user':'Élodie','currency':'USD','amount':'-1.25'}]
            source.write_text('\n'.join(json.dumps(x,ensure_ascii=False) if isinstance(x,dict) else x for x in rows)+'\n\n')
            p=call(source,'--output',output);assert p.returncode==0,p.stderr
            expected={'records':3,'totals':{'EUR':'0.30','USD':'-1.25'},'users':['Élodie','李'],'invalid_rows':2,'duplicate_rows':1}
            assert json.loads(p.stdout)==expected,p.stdout
            assert json.loads(output.read_text())==expected
        '''),
        check('pipeline-strict','Strict failures never overwrite the previous output; empty input is valid','pipeline.py',r'''
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'input.jsonl';output=Path(d)/'report.json'
            output.write_text('{"preserve": true}\n');before=output.read_bytes()
            source.write_text(json.dumps({'id':'ok','user':'A','currency':'EUR','amount':'1.00'})+'\ninvalid\n')
            p=call(source,'--output',output,'--strict')
            assert p.returncode==2 and not p.stdout.strip() and p.stderr.strip(),(p.returncode,p.stdout,p.stderr)
            assert output.read_bytes()==before
            source.write_text('\n   \n')
            p=call(source,'--output',output,'--strict');assert p.returncode==0,p.stderr
            assert json.loads(p.stdout)=={'records':0,'totals':{},'users':[],'invalid_rows':0,'duplicate_rows':0},p.stdout
        '''),
        check('pipeline-unseen','Seeded unseen amounts, currencies, users and invalid schemas','pipeline.py',r'''
        import random
        from decimal import Decimal
        rng=random.Random(517029)
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'input.jsonl';output=Path(d)/'report.json';totals={};users=set();rows=[]
            for i in range(100):
                currency=rng.choice(['EUR','USD','JPY']);amount=Decimal(rng.randrange(-99999,99999))/100;user=rng.choice(['Zoé','A','李'])
                totals[currency]=totals.get(currency,Decimal(0))+amount;users.add(user)
                rows.append({'id':f'id-{i}','user':user,'currency':currency,'amount':format(amount,'.2f')})
            rows.extend([{'id':'id-0','user':'A','currency':'EUR','amount':'1e2'},{'id':3,'user':'A','currency':'EUR','amount':'2.00'},{'id':'bad1','user':' ','currency':'EUR','amount':'1.00'},{'id':'bad2','user':'A','currency':'eur','amount':'1.00'},{'id':'bad3','user':'A','currency':'USD','amount':'1.234'}])
            source.write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in rows)+'\n')
            p=call(source,'--output',output);assert p.returncode==0,p.stderr
            expected={'records':100,'totals':{k:format(v,'.2f') for k,v in totals.items()},'users':sorted(users),'invalid_rows':5,'duplicate_rows':0}
            assert json.loads(p.stdout)==expected,(p.stdout,expected)
        '''),
    ]
    return [
        {'name':'inventory','goal':'Termine cet outil pour que je puisse gérer mon petit stock au quotidien, importer mes articles et retrouver mes données sans mauvaise surprise. Prends les décisions nécessaires et laisse un projet utilisable.',
         'files':{'README.md':INVENTORY_README,'inventory.py':"import json\nfrom storage import load\nprint(json.dumps(load(None)))\n",'storage.py':"import json\ndef load(path):\n    return []\ndef save(path, rows):\n    path.write_text(json.dumps(rows))\n",'validation.py':"def quantity(text):\n    return float(text)\n"},'checks':inventory},
        {'name':'agenda','goal':'Rends cet agenda de salles utilisable et fiable. Je veux réserver, retrouver et supprimer mes créneaux, avec une protection contre les conflits et la conservation des réservations.',
         'files':{'README.md':AGENDA_README,'agenda.py':"import json\nprint(json.dumps([]))\n",'database.py':"import sqlite3\ndef connect(path):\n    return sqlite3.connect(path)\n",'dates.py':"def parse(value):\n    return value\n"},'checks':agenda},
        {'name':'pipeline','goal':'Fais de ce prototype un importeur de transactions fiable qui produit une synthèse exploitable. Gère les données sales et protège le rapport précédent lorsqu’un traitement strict échoue.',
         'files':{'README.md':PIPELINE_README,'pipeline.py':"import json\nprint(json.dumps({'records':0}))\n",'parsing.py':"import json\ndef parse(line):\n    return json.loads(line)\n",'aggregation.py':"def total(records):\n    return sum(float(x['amount']) for x in records)\n"},'checks':pipeline},
    ]
