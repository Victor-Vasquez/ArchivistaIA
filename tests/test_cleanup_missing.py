import contextlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from core import cleanup_missing as cleanup


class CleanupTests(unittest.TestCase):
    def test_simulation_and_apply_preserve_history(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'temp') as folder:
            path = Path(folder) / 'catalog.db'
            db = sqlite3.connect(path)
            db.executescript('''
                CREATE TABLE archivos(id INTEGER PRIMARY KEY, ruta TEXT, existe INTEGER);
                CREATE TABLE legacy(archivo_id INTEGER);
                CREATE TABLE other(file_ref INTEGER REFERENCES archivos(id));
                INSERT INTO archivos VALUES (1,'absent',0),(2,'historical',0),
                    (3,'active',1),(4,'foreign',0);
                INSERT INTO legacy VALUES (2);
                INSERT INTO other VALUES (4);
            ''')
            db.commit()
            self.assertEqual(cleanup.selection(db), ({1, 2, 4}, {2, 4}, [1]))
            db.close()
            with patch.object(cleanup, 'DATABASE', path), contextlib.redirect_stdout(io.StringIO()):
                with patch('sys.argv', ['cleanup']):
                    cleanup.main()
                self.assertFalse((path.parent / 'backups').exists())
                with patch('sys.argv', ['cleanup', '--apply']):
                    cleanup.main()
            db = sqlite3.connect(path)
            try:
                self.assertEqual(db.execute('SELECT id FROM archivos ORDER BY id').fetchall(),
                                 [(2,), (3,), (4,)])
                self.assertEqual(db.execute('SELECT * FROM legacy').fetchall(), [(2,)])
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            finally:
                db.close()
            archives = list((path.parent / 'backups').glob('*.jsonl'))
            self.assertEqual(json.loads(archives[0].read_text())['id'], 1)
            backup = sqlite3.connect(next((path.parent / 'backups').glob('*.db')))
            try:
                self.assertEqual(backup.execute('SELECT COUNT(*) FROM archivos').fetchone()[0], 4)
            finally:
                backup.close()


if __name__ == '__main__':
    unittest.main()
