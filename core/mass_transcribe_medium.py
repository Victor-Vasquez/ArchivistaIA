"""Resumable MEDIUM transcription. Originals and legacy tables are read-only."""
import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import logging
import math
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / 'data' / 'archivista.db'
FFMPEG = Path(r'C:\vvasquez\apps\ffmpeg\bin\ffmpeg.exe')
TEMP = ROOT / 'temp' / 'medium'
LOG = ROOT / 'logs' / 'mass_transcribe_medium.log'
OPTIONS = dict(language='es', beam_size=1, vad_filter=True, condition_on_previous_text=False)
CONFIG = dict(model='medium', device='cpu', compute_type='int8', **OPTIONS,
              faster_whisper=importlib.metadata.version('faster-whisper'),
              ctranslate2=importlib.metadata.version('ctranslate2'), pipeline_version=1)
CONFIG_JSON = json.dumps(CONFIG, sort_keys=True, separators=(',', ':'))
# Only the configuration is hashed. Multimedia hashes are NEVER recalculated.
CONFIG_KEY = hashlib.sha256(CONFIG_JSON.encode()).hexdigest()
CANDIDATES = "a.existe=1 AND (a.tipo IN ('AUDIO','VIDEO') OR lower(a.ruta) LIKE '%.vob')"
SCHEMA = '''
CREATE TABLE IF NOT EXISTS medium_runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 archivo_id INTEGER NOT NULL REFERENCES archivos(id),
 modelo TEXT NOT NULL, config_key TEXT NOT NULL, config_json TEXT NOT NULL,
 estado TEXT NOT NULL CHECK(estado IN ('PROCESANDO','COMPLETADO','ERROR','INTERRUMPIDO')),
 source_hash TEXT, source_size INTEGER, source_mtime_ns INTEGER,
 inicio_ts TEXT NOT NULL, fin_ts TEXT, tiempo_segundos REAL,
 segmentos INTEGER, modo TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS medium_segments (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 run_id INTEGER NOT NULL REFERENCES medium_runs(id),
 archivo_id INTEGER NOT NULL REFERENCES archivos(id),
 inicio REAL NOT NULL, fin REAL NOT NULL, texto TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS medium_files (
 archivo_id INTEGER NOT NULL REFERENCES archivos(id),
 config_key TEXT NOT NULL,
 run_id INTEGER NOT NULL REFERENCES medium_runs(id),
 asociado_ts TEXT NOT NULL, reutilizado INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(archivo_id,config_key)
);
CREATE INDEX IF NOT EXISTS idx_medium_segments_run ON medium_segments(run_id);
CREATE INDEX IF NOT EXISTS idx_medium_runs_hash ON medium_runs(config_key,source_hash,estado);
CREATE INDEX IF NOT EXISTS idx_medium_files_run ON medium_files(run_id);
'''


def now():
    return datetime.now(timezone.utc).isoformat()


@contextlib.contextmanager
def connection(readonly=False):
    uri = DATABASE.resolve().as_uri() + ('?mode=ro' if readonly else '?mode=rw')
    db = sqlite3.connect(uri, uri=True, timeout=60)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=60000')
    db.execute('PRAGMA temp_store=MEMORY')
    try:
        yield db
        if not readonly:
            db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


@contextlib.contextmanager
def single_worker():
    import msvcrt
    lock = ROOT / 'logs' / 'mass_transcribe_medium.lock'
    lock.parent.mkdir(exist_ok=True)
    with lock.open('a+b') as handle:
        if handle.seek(0, 2) == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError('Another MEDIUM worker holds the lock') from exc
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def prepare():
    # Every invocation that may create schema first makes a consistent SQLite backup.
    backup_dir = ROOT / 'data' / 'backups'
    backup_dir.mkdir(exist_ok=True)
    target = backup_dir / ('archivista_before_medium_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.db')
    with connection(readonly=True) as source:
        dest = sqlite3.connect(target)
        try:
            source.backup(dest)
            if dest.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup verification failed')
        finally:
            dest.close()
    logging.info('BACKUP %s', target)
    with connection() as db:
        db.executescript(SCHEMA)
    logging.info('SCHEMA ready config=%s', CONFIG_KEY)
    return target


def candidates():
    with connection(readonly=True) as db:
        rows = db.execute('SELECT a.* FROM archivos a WHERE ' + CANDIDATES + ' ORDER BY a.id').fetchall()
    return [dict(r) for r in rows]


def completed(archivo_id):
    with connection(readonly=True) as db:
        return db.execute('''SELECT r.* FROM medium_files f JOIN medium_runs r ON r.id=f.run_id
            WHERE f.archivo_id=? AND f.config_key=? AND r.estado='COMPLETADO' ''',
            (archivo_id, CONFIG_KEY)).fetchone()


def summary():
    with connection(readonly=True) as db:
        total = db.execute('SELECT COUNT(*) FROM archivos a WHERE ' + CANDIDATES).fetchone()[0]
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='medium_files'").fetchone()
        done = 0 if not exists else db.execute('''SELECT COUNT(*) FROM archivos a JOIN medium_files f
            ON f.archivo_id=a.id JOIN medium_runs r ON r.id=f.run_id WHERE ''' + CANDIDATES +
            " AND f.config_key=? AND r.estado='COMPLETADO'", (CONFIG_KEY,)).fetchone()[0]
    return dict(total=total, completados=done, pendientes=total-done, config_key=CONFIG_KEY)


def signature(path):
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(path)
    stat = p.stat()
    return stat.st_size, stat.st_mtime_ns


def trusted_hash(row, sig):
    value = row.get('hash_archivo')
    if not isinstance(value, str) or not re.fullmatch('[0-9a-fA-F]{64}', value):
        return None
    try:
        recorded = float(row['fecha_modificacion'])
        if row['tamano'] != sig[0] or not math.isfinite(recorded):
            return None
        if abs(recorded - sig[1] / 1e9) > 0.001:
            return None
    except (TypeError, ValueError):
        return None
    return value.lower()


def reusable(row, sig):
    digest = trusted_hash(row, sig)
    if not digest:
        return None
    with connection(readonly=True) as db:
        matches = db.execute('''SELECT r.id AS run_id,r.source_size,r.source_mtime_ns,a.*
            FROM medium_runs r JOIN archivos a ON a.id=r.archivo_id
            WHERE r.config_key=? AND r.source_hash=? AND r.estado='COMPLETADO' AND a.existe=1''',
            (CONFIG_KEY, digest)).fetchall()
    for match in matches:
        source = dict(match)
        try:
            current = signature(source['ruta'])
            if (current == (source['source_size'], source['source_mtime_ns'])
                    and current[0] == sig[0] and trusted_hash(source, current) == digest):
                return source['run_id']
        except OSError:
            continue
    return None


def associate(db, archivo_id, run_id, reused):
    db.execute('''INSERT INTO medium_files(archivo_id,config_key,run_id,asociado_ts,reutilizado)
        VALUES (?,?,?,?,?)''', (archivo_id, CONFIG_KEY, run_id, now(), int(reused)))


def begin_run(row, sig):
    with connection() as db:
        cursor = db.execute('''INSERT INTO medium_runs(archivo_id,modelo,config_key,config_json,
            estado,source_hash,source_size,source_mtime_ns,inicio_ts)
            VALUES (?,'medium',?,?,'PROCESANDO',?,?,?,?)''',
            (row['id'], CONFIG_KEY, CONFIG_JSON, trusted_hash(row, sig), sig[0], sig[1], now()))
        return cursor.lastrowid


def finish(run_id, row, segments, mode, elapsed):
    with connection() as db:
        db.executemany('''INSERT INTO medium_segments(run_id,archivo_id,inicio,fin,texto)
            VALUES (?,?,?,?,?)''', ((run_id, row['id'], s, e, t) for s, e, t in segments))
        db.execute('''UPDATE medium_runs SET estado='COMPLETADO',fin_ts=?,tiempo_segundos=?,
            segmentos=?,modo=? WHERE id=?''', (now(), elapsed, len(segments), mode, run_id))
        associate(db, row['id'], run_id, False)


def fail(run_id, state, error, elapsed):
    with connection() as db:
        db.execute('UPDATE medium_runs SET estado=?,fin_ts=?,error=?,tiempo_segundos=? WHERE id=?',
                   (state, now(), str(error)[:12000], elapsed, run_id))


def consume(model, path):
    segments, _ = model.transcribe(str(path), **OPTIONS)
    result = []
    for segment in segments:
        start, end = float(segment.start), float(segment.end)
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start:
            raise ValueError('Invalid segment timestamps')
        result.append((start, end, segment.text))
    return result


def transcribe(model, path, force_fallback=False):
    if not force_fallback:
        try:
            return consume(model, path), 'directo'
        except Exception:
            logging.exception('Direct decoding/transcription failed; trying FFmpeg: %s', path)
    TEMP.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='medium_', suffix='.wav', dir=TEMP)
    os.close(fd)
    wav = Path(name)
    try:
        result = subprocess.run([str(FFMPEG), '-nostdin', '-hide_banner', '-loglevel', 'error',
            '-i', str(path), '-map', '0:a:0', '-vn', '-ac', '1', '-ar', '16000',
            '-c:a', 'pcm_s16le', '-y', str(wav)], capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=7200,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise RuntimeError('FFmpeg: ' + result.stderr[-6000:])
        return consume(model, wav), 'ffmpeg'
    finally:
        # The ONLY deletion in this program: this invocation's own temporary WAV.
        wav.unlink(missing_ok=True)


def process(model, row, force_fallback=False):
    if completed(row['id']):
        logging.info('SKIP completed id=%s', row['id'])
        return 'omitido'
    started = time.monotonic()
    # Missing/corrupt files must also have a persisted ERROR attempt.
    try:
        sig = signature(row['ruta'])
    except OSError as exc:
        run_id = begin_run(row, (None, None))
        fail(run_id, 'ERROR', exc, time.monotonic()-started)
        logging.exception('ERROR inaccessible id=%s ruta=%s', row['id'], row['ruta'])
        return 'error'
    existing = reusable(row, sig)
    if existing is not None:
        with connection() as db:
            associate(db, row['id'], existing, True)
        logging.info('REUSED id=%s run=%s ruta=%s', row['id'], existing, row['ruta'])
        return 'reutilizado'
    run_id = begin_run(row, sig)
    stop = threading.Event()
    def heartbeat():
        while not stop.wait(45):
            logging.info('WORKING id=%s run=%s elapsed=%.1fs ruta=%s', row['id'], run_id,
                         time.monotonic()-started, row['ruta'])
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        segments, mode = transcribe(model, row['ruta'], force_fallback)
        if signature(row['ruta']) != sig:
            raise RuntimeError('Source changed during transcription; result not committed')
        elapsed = time.monotonic()-started
        finish(run_id, row, segments, mode, elapsed)
        logging.info('COMPLETADO id=%s run=%s segmentos=%s modo=%s duracion=%.2fs',
                     row['id'], run_id, len(segments), mode, elapsed)
        return 'completado'
    except KeyboardInterrupt:
        fail(run_id, 'INTERRUMPIDO', 'KeyboardInterrupt', time.monotonic()-started)
        raise
    except Exception as exc:
        fail(run_id, 'ERROR', repr(exc), time.monotonic()-started)
        logging.exception('ERROR id=%s ruta=%s', row['id'], row['ruta'])
        return 'error'
    finally:
        stop.set()
        thread.join(timeout=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--file-id', type=int)
    parser.add_argument('--force-fallback', action='store_true', help='Controlled one-file validation only')
    args = parser.parse_args()
    if sys.version_info[:3] != (3, 12, 10):
        raise RuntimeError('Python 3.12.10 required')
    if args.force_fallback and not args.file_id:
        parser.error('--force-fallback requires --file-id')
    if args.dry_run:
        print(json.dumps(summary(), ensure_ascii=True))
        return
    LOG.parent.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s',
        handlers=[logging.FileHandler(LOG, encoding='utf-8'), logging.StreamHandler(sys.stdout)])
    with single_worker():
        if args.prepare:
            prepare()
            print(json.dumps(summary()))
            return
        if not Path('E:/').is_dir() or not FFMPEG.is_file():
            raise RuntimeError('E: or FFmpeg unavailable')
        logging.info('START pid=%s executable=%s config=%s', os.getpid(), sys.executable, CONFIG_JSON)
        with connection() as db:
            db.execute("UPDATE medium_runs SET estado='INTERRUMPIDO',fin_ts=?,error=? WHERE estado='PROCESANDO'",
                       (now(), 'Previous worker stopped before completion; preserved attempt'))
        rows = candidates()
        initial = summary()
        logging.info('GLOBAL initial=%s', initial)
        if args.file_id:
            rows = [r for r in rows if r['id'] == args.file_id]
            if not rows:
                raise RuntimeError('Requested file is not an active multimedia candidate')
        # Load completion IDs once instead of opening SQLite for every candidate.
        with connection(readonly=True) as db:
            done_ids = {r[0] for r in db.execute(
                "SELECT f.archivo_id FROM medium_files f JOIN medium_runs r ON r.id=f.run_id "
                "WHERE f.config_key=? AND r.estado='COMPLETADO'", (CONFIG_KEY,))}
        rows = [r for r in rows if r['id'] not in done_ids]
        if not rows:
            logging.info('No pending files; no model loaded')
            return
        from faster_whisper import WhisperModel
        logging.info('Loading MEDIUM once')
        logging.info('CPU threads=2 (benchmarked on this machine); single worker')
        model = WhisperModel('medium', device='cpu', compute_type='int8', cpu_threads=2)
        logging.info('MODEL READY')
        counters = dict(completado=0, reutilizado=0, error=0, omitido=0)
        for index, row in enumerate(rows, 1):
            logging.info('FILE %s/%s id=%s ruta=%s', index, len(rows), row['id'], row['ruta'])
            outcome = process(model, row, args.force_fallback)
            counters[outcome] += 1
            logging.info('GLOBAL processed=%s/%s outcomes=%s', index, len(rows), counters)
        logging.info('FINISHED summary=%s outcomes=%s', summary(), counters)
        if args.file_id and counters['error']:
            raise RuntimeError('Controlled transcription failed')


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        logging.exception('WORKER STOPPED')
        raise
