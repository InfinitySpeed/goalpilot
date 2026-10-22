from pathlib import Path
import sqlite3

LEDGER = '''# Ledger: local money transfers
Finish this prototype as a dependable local transfer tool. Python stdlib only.
CLI: python ledger.py --db PATH transfer --id KEY --from ACCOUNT --to ACCOUNT --amount DECIMAL;
import --file CSV; balances; history.
All successful commands print one JSON value; errors exit2, useful stderr, no stdout.
Existing SQLite accounts(name TEXT PRIMARY KEY,cents INTEGER NOT NULL) holds user balances.
Migrate it in place, preserving balances, names and unrelated tables. Never reset data. Create parent directories; a fresh database starts with no accounts.
transfer and CSV rows have fields id,from,to,amount. IDs and account names are nonblank strings. The accounts must exist and differ. Amount is a string in plain decimal notation (e.g. 1, 1.20, 0.01), >0, at most two fractional digits, no exponents/NaN/infinity/whitespace/signs. Arithmetic is exact integer cents. Reject insufficient funds.
Successful transfer prints {"id":str,"from":str,"to":str,"cents":int}. Same ID and same normalized accounts/cents is an idempotent replay returning the original object even if the account now lacks funds; different content for the same ID is an error. Transfer transaction updates both balances and history atomically.
CSV is UTF-8, header exactly id,from,to,amount, supports quoted Unicode fields. Import the WHOLE file in one transaction; bad headers, extra/missing fields, malformed CSV, invalid amount, insufficient funds or conflicting ID anywhere rolls back all rows and any new history. Apply rows in file order. Duplicate identical IDs are replayed without a second debit. Print a transfer object per input row as a JSON array, including replays.
balances prints [{"account":str,"cents":int},...] in account-name order. history prints transfer objects in first-application order, excluding replays.
Concurrent separate processes must not overspend or lose money. Corrupt databases fail cleanly without replacement. Preserve the existing data/legacy.sqlite and USER_NOTES.txt. Deliver documentation and meaningful own tests. No services or dependencies.
'''
SYNC = '''# Sync: safe one-way working-folder synchronization
Finish this local sync tool with state tracking, conflict detection and usable diagnostics. Stdlib Python only.
CLI: python sync.py --state STATE sync SOURCE DEST; status.
sync successful JSON: {"copied":[relative paths],"deleted":[relative paths],"unchanged":[relative paths]}, each lexicographically sorted. status prints parsed state, or {"version":1,"files":{}} when absent.
State schema {"version":1,"files":{POSIX_relative_path:lowercase_sha256}} records the last successful source/destination contents. Write it using atomic replace only after successful sync. Create missing destination/state parent directories. SOURCE must be an existing directory.
Recursively include regular source files (dotfiles, Unicode, empty files); skip all symlinks. Do not traverse symlink directories. Empty directories need not sync. Copy bytes exactly, including binary data. The state file must lie outside both source and destination trees; source and destination must not overlap in either direction, including aliases through symlinks.
First sync: a destination file not in state may be adopted if it has the same contents; differing existing destination files conflict. Preserve all destination files absent from both source and state.
Later sync: for each tracked path, destination must still match the recorded hash or the current source hash. Otherwise report a conflict, including locally edited destination when source was deleted. Missing destination is allowed only if source still exists (recopy it). If both source and destination vanished, drop it from state. When source removed a tracked file and destination still matches baseline, delete it. Recopy changed source only when safe. Unchanged means a source file is already equal at destination; no rewrite is needed.
Preflight the ENTIRE batch before ANY destination/state modification. Any conflict, unsafe path or invalid state exits2, useful stderr, no stdout, and leaves destination and state byte-for-byte unchanged. In particular a batch containing one changed source file and one conflicting destination must copy neither. Reject destination symlink files/parents, non-directory parents and non-regular targets; preserve their targets. Never follow links during deletion. Source/destination roots cannot be symlinks.
Validate state version, hash syntax and paths for every command: no absolute paths, .., empty segments, backslashes, drive prefixes or duplicate JSON keys; version bool is invalid. No deletion outside dest; no guessing that a corrupt state is empty. Rejected state bytes must remain unchanged. Preserve USER_NOTES.txt and unrelated files. Document and test normal paths, errors, deletion and restart behavior. No network/deployment.
'''


def cases():
    return [dict(name='ledger',goal='Rends ce prototype fiable pour gérer mes virements et importer mes opérations sans perdre ni dupliquer de l’argent. Termine les cas difficiles et teste le résultat.',readme=LEDGER,entry='ledger.py'),
            dict(name='sync',goal='Termine cet outil pour synchroniser mon travail entre deux dossiers en sécurité, reprendre après plusieurs utilisations et protéger mes modifications. Livre quelque chose d’utilisable et testé.',readme=SYNC,entry='sync.py')]


def materialize(case,repo):
    repo=Path(repo);repo.mkdir(parents=True)
    (repo/'README.md').write_text(case['readme'])
    (repo/'USER_NOTES.txt').write_text('Mes données: café 東京\n')
    (repo/case['entry']).write_text('from core import main\nif __name__ == "__main__": main()\n')
    (repo/'core.py').write_text('def main():\n    raise RuntimeError("prototype incomplete")\n')
    if case['name']=='ledger':
        (repo/'data').mkdir()
        with sqlite3.connect(repo/'data/legacy.sqlite') as db:
            db.execute('create table accounts(name text primary key,cents integer not null)')
            db.executemany('insert into accounts values(?,?)',[('alice',10000),('bob',250),('東京, café',1000)])
            db.execute('create table personal_notes(content text)')
            db.execute('insert into personal_notes values(?)',('keep me',))
