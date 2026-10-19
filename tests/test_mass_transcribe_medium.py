from contextlib import contextmanager
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from core import mass_transcribe_medium as m


class MediumTests(unittest.TestCase):
    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.db)
        try:
            with db:
                yield db
        finally:
            db.close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / 'test.db'
        with self.connection() as db:
            db.execute('''CREATE TABLE archivos(id INTEGER PRIMARY KEY,ruta TEXT,tamano INTEGER,
                       fecha_modificacion TEXT,hash_archivo TEXT,tipo TEXT,existe INTEGER)''')
            db.executescript(m.SCHEMA)
        self.patches = [patch.object(m, 'DATABASE', self.db), patch.object(m, 'TEMP', self.root / 'wav')]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def row(self, ident=1, digest='a'*64, tipo='AUDIO', existe=1):
        path = self.root / (str(ident) + '.vob')
        path.write_bytes(b'test audio placeholder')
        st = path.stat()
        row = dict(id=ident,ruta=str(path),tamano=st.st_size,fecha_modificacion=str(st.st_mtime),
                   hash_archivo=digest,tipo=tipo,existe=existe)
        with self.connection() as db:
            db.execute('INSERT INTO archivos VALUES (:id,:ruta,:tamano,:fecha_modificacion,:hash_archivo,:tipo,:existe)',row)
        return row

    def test_selection_includes_old_vob_excludes_inactive(self):
        self.row(tipo='OTRO')
        self.row(2, existe=0)
        with self.connection() as db:
            db.execute("UPDATE archivos SET fecha_modificacion='0'")
        self.assertEqual([r['id'] for r in m.candidates()], [1])

    def test_zero_segments_completed_and_resume_no_transcription(self):
        row = self.row()
        with patch.object(m, 'transcribe', return_value=([], 'directo')) as transcribe:
            self.assertEqual(m.process(None,row),'completado')
            self.assertEqual(m.process(None,row),'omitido')
            self.assertEqual(transcribe.call_count,1)
        self.assertEqual(m.completed(1)['segmentos'],0)

    def test_failure_is_persisted_retry_appends_attempt(self):
        row = self.row()
        with patch.object(m, 'transcribe', side_effect=ValueError('corrupt')):
            self.assertEqual(m.process(None,row),'error')
        with patch.object(m, 'transcribe', return_value=([(0,1,'hola')],'directo')):
            self.assertEqual(m.process(None,row),'completado')
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT estado FROM medium_runs ORDER BY id').fetchall(),[('ERROR',),('COMPLETADO',)])

    def test_atomic_rollback(self):
        row=self.row()
        run=m.begin_run(row,m.signature(row['ruta']))
        with patch.object(m,'associate',side_effect=RuntimeError('commit boundary')):
            with self.assertRaises(RuntimeError):
                m.finish(run,row,[(0,1,'hola')],'directo',1)
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM medium_segments').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT estado FROM medium_runs').fetchone()[0],'PROCESANDO')
        self.assertIsNone(m.completed(1))

    def test_valid_duplicate_reuses_completed_run(self):
        first=self.row()
        other=self.row(2)
        with patch.object(m,'transcribe',return_value=([(0,1,'hola')],'directo')) as transcribe:
            m.process(None,first)
            self.assertEqual(m.process(None,other),'reutilizado')
            self.assertEqual(transcribe.call_count,1)
        self.assertEqual(m.completed(1)['id'],m.completed(2)['id'])

    def test_invalid_or_stale_hash_not_reused(self):
        row=self.row(digest='PRUEBA')
        sig=m.signature(row['ruta'])
        self.assertIsNone(m.trusted_hash(row,sig))
        row['hash_archivo']='a'*64
        row['tamano']+=1
        self.assertIsNone(m.trusted_hash(row,sig))

    def test_missing_file_records_error(self):
        row=self.row()
        Path(row['ruta']).unlink()
        self.assertEqual(m.process(None,row),'error')
        with self.connection() as db:
            self.assertEqual(db.execute('SELECT estado FROM medium_runs').fetchone()[0],'ERROR')

    def test_fallback_cleanup_and_options(self):
        row=self.row()
        result=Mock(returncode=0,stderr='')
        with patch.object(m,'consume',side_effect=[ValueError('PyAV'),[(0,1,'hola')]]), patch.object(m.subprocess,'run',return_value=result) as ff:
            segments,mode=m.transcribe(None,row['ruta'])
        self.assertEqual(mode,'ffmpeg')
        args=ff.call_args.args[0]
        self.assertEqual(args[args.index('-ar')+1],'16000')
        self.assertEqual(args[args.index('-ac')+1],'1')
        self.assertEqual(list(m.TEMP.glob('*.wav')),[])
        self.assertTrue(Path(row['ruta']).exists())
        with patch.object(m.subprocess,'run',side_effect=RuntimeError('ffmpeg fails')):
            with self.assertRaises(RuntimeError):
                m.transcribe(None,row['ruta'],True)
        self.assertEqual(list(m.TEMP.glob('*.wav')),[])


if __name__ == '__main__':
    unittest.main()
