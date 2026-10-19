import sqlite3
import time
import traceback
from datetime import datetime

from faster_whisper import WhisperModel

from config.settings import DATABASE


FECHA_MINIMA = 1690848000  # 2023-08-01

_modelo = None


def obtener_modelo():
    global _modelo

    if _modelo is None:
        print("Cargando Whisper small...")

        _modelo = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8",
        )

    return _modelo


def preparar_base():
    db = sqlite3.connect(DATABASE)

    db.execute("""
        CREATE TABLE IF NOT EXISTS transcripciones_small (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            archivo_id INTEGER NOT NULL,
            inicio REAL NOT NULL,
            fin REAL NOT NULL,
            texto TEXT NOT NULL,
            FOREIGN KEY (archivo_id)
                REFERENCES archivos(id)
        )
    """)

    db.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_transcripciones_small_archivo
        ON transcripciones_small(archivo_id)
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS transcripcion_small_estado (
            archivo_id INTEGER PRIMARY KEY,
            estado TEXT NOT NULL,
            segmentos INTEGER DEFAULT 0,
            tiempo_segundos REAL,
            fecha_revision TEXT,
            error TEXT,
            FOREIGN KEY (archivo_id)
                REFERENCES archivos(id)
        )
    """)

    db.commit()
    db.close()


def obtener_archivos():
    db = sqlite3.connect(DATABASE)
    c = db.cursor()

    c.execute("""
        SELECT
            a.id,
            a.ruta,
            a.hash_archivo
        FROM archivos a
        WHERE a.tipo IN ('AUDIO', 'VIDEO')
          AND CAST(a.fecha_modificacion AS REAL) >= ?
          AND NOT EXISTS (
              SELECT 1
              FROM transcripcion_small_estado e
              WHERE e.archivo_id = a.id
                AND e.estado = 'COMPLETADO'
          )
        ORDER BY CAST(a.fecha_modificacion AS REAL) DESC
    """, (FECHA_MINIMA,))

    filas = c.fetchall()
    db.close()

    hashes = set()
    resultado = []

    for archivo_id, ruta, hash_archivo in filas:

        if hash_archivo:
            if hash_archivo in hashes:
                continue

            hashes.add(hash_archivo)

        resultado.append(
            (archivo_id, ruta)
        )

    return resultado


def guardar_estado(
    archivo_id,
    estado,
    segmentos=0,
    tiempo_segundos=None,
    error=None,
):
    db = sqlite3.connect(
        DATABASE,
        timeout=60
    )

    db.execute(
        "PRAGMA busy_timeout=60000"
    )

    db.execute("""
        INSERT OR REPLACE INTO transcripcion_small_estado (
            archivo_id,
            estado,
            segmentos,
            tiempo_segundos,
            fecha_revision,
            error
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        archivo_id,
        estado,
        segmentos,
        tiempo_segundos,
        datetime.now().isoformat(),
        error,
    ))

    db.commit()
    db.close()


def borrar_transcripcion_anterior(
    db,
    archivo_id
):
    db.execute("""
        DELETE FROM transcripciones_small
        WHERE archivo_id = ?
    """, (archivo_id,))


def transcribir_archivo(
    archivo_id,
    ruta
):
    modelo = obtener_modelo()

    print()
    print("Transcribiendo:")
    print(ruta)

    segmentos, info = modelo.transcribe(
        ruta,
        language="es",
        beam_size=1,
        vad_filter=True,
        condition_on_previous_text=False,
    )

    db = sqlite3.connect(
        DATABASE,
        timeout=60
    )

    db.execute(
        "PRAGMA busy_timeout=60000"
    )

    borrar_transcripcion_anterior(
        db,
        archivo_id
    )

    cantidad = 0

    try:
        for segmento in segmentos:

            texto = segmento.text.strip()

            if not texto:
                continue

            db.execute("""
                INSERT INTO transcripciones_small (
                    archivo_id,
                    inicio,
                    fin,
                    texto
                )
                VALUES (?, ?, ?, ?)
            """, (
                archivo_id,
                segmento.start,
                segmento.end,
                texto,
            ))

            cantidad += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    return cantidad


def main():
    preparar_base()

    archivos = obtener_archivos()

    print("=" * 72)
    print("ARCHIVISTA IA - TRANSCRIPCION MASIVA")
    print("Whisper small")
    print("=" * 72)

    print(
        "Archivos pendientes:",
        len(archivos)
    )

    inicio_total = time.time()

    completados = 0
    errores = 0

    for numero, (
        archivo_id,
        ruta
    ) in enumerate(archivos, 1):

        print()
        print("#" * 72)

        print(
            f"ARCHIVO {numero}/"
            f"{len(archivos)}"
        )

        print(f"ID: {archivo_id}")
        print(ruta)

        print("#" * 72)

        inicio = time.time()

        guardar_estado(
            archivo_id,
            "PROCESANDO"
        )

        try:
            cantidad = transcribir_archivo(
                archivo_id,
                ruta
            )

            duracion = (
                time.time() - inicio
            )

            guardar_estado(
                archivo_id,
                "COMPLETADO",
                cantidad,
                duracion,
                None,
            )

            completados += 1

            print()
            print(
                f"Segmentos guardados: "
                f"{cantidad}"
            )

            print(
                f"Tiempo: "
                f"{duracion / 60:.1f} min"
            )

        except KeyboardInterrupt:
            guardar_estado(
                archivo_id,
                "INTERRUMPIDO",
                error="Interrumpido"
            )

            print()
            print("Proceso interrumpido.")

            break

        except Exception as e:
            errores += 1

            error = (
                f"{type(e).__name__}: {e}"
            )

            guardar_estado(
                archivo_id,
                "ERROR",
                error=error,
            )

            print()
            print(
                f"ERROR ID {archivo_id}"
            )

            print(error)

            traceback.print_exc()

            print()
            print(
                "Continuando con el "
                "siguiente archivo..."
            )

    tiempo_total = (
        time.time() -
        inicio_total
    )

    print()
    print("=" * 72)
    print("RESUMEN")
    print("=" * 72)

    print(
        "Completados:",
        completados
    )

    print(
        "Errores:",
        errores
    )

    print(
        "Tiempo:",
        f"{tiempo_total / 3600:.2f}",
        "horas"
    )


if __name__ == "__main__":
    main()