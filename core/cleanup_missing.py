"""Remove catalog entries already marked absent, protecting all related history."""
import argparse
import json
from datetime import datetime
from pathlib import Path
import sqlite3

DATABASE = Path(__file__).resolve().parents[1] / 'data' / 'archivista.db'


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def selection(db):
    absent = {r[0] for r in db.execute('SELECT id FROM archivos WHERE existe=0')}
    protected = set()
    tables = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    for table in tables:
        if table == 'archivos':
            continue
        columns = {r[1] for r in db.execute('PRAGMA table_info(' + quoted(table) + ')')}
        references = {'archivo_id'} if 'archivo_id' in columns else set()
        for fk in db.execute('PRAGMA foreign_key_list(' + quoted(table) + ')'):
            if fk[2] == 'archivos':
                if fk[4] != 'id':
                    raise RuntimeError('Unsupported reference to archivos: ' + table)
                references.add(fk[3])
        for column in references:
            protected.update(r[0] for r in db.execute(
                'SELECT a.id FROM archivos a JOIN ' + quoted(table) + ' t ON t.'
                + quoted(column) + '=a.id WHERE a.existe=0'))
    return absent, protected, sorted(absent - protected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Back up and delete eligible catalog rows')
    args = parser.parse_args()
    db = sqlite3.connect(DATABASE.as_uri() + ('?mode=rw' if args.apply else '?mode=ro'),
                         uri=True, timeout=15)
    try:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA temp_store=MEMORY')
        if not args.apply:
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
        else:
            backup_dir = DATABASE.parent / 'backups'
            backup_dir.mkdir(exist_ok=True)
            backup = backup_dir / ('archivista_before_cleanup_' +
                                  datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.db')
            target = sqlite3.connect(backup)
            try:
                db.backup(target)
                if target.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Backup verification failed; no deletion performed')
            finally:
                target.close()
            print('Backup:', backup)
            db.execute('BEGIN IMMEDIATE')
        absent, protected, eligible = selection(db)
        print(json.dumps(dict(mode='apply' if args.apply else 'simulation',
                              absent=len(absent), protected=len(protected), eligible=len(eligible))))
        if args.apply:
            # Preserve exact deleted rows even if the catalog changed after backup.
            archive = backup.with_suffix('.removed.jsonl')
            db.row_factory = sqlite3.Row
            with archive.open('x', encoding='utf-8') as output:
                for ident in eligible:
                    row = db.execute('SELECT * FROM archivos WHERE id=? AND existe=0', (ident,)).fetchone()
                    output.write(json.dumps(dict(row), ensure_ascii=False) + '\n')
                output.flush()
            db.executemany('DELETE FROM archivos WHERE id=? AND existe=0', ((i,) for i in eligible))
            db.commit()
            print('Removed catalog rows:', len(eligible), 'Archive:', archive)
    finally:
        db.rollback()
        db.close()


if __name__ == '__main__':
    main()
