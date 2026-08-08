import sqlite3

from faster_whisper import WhisperModel

from config.settings import DATABASE


_modelo = None


def obtener_modelo():
    global _modelo

    if _modelo is None:
        print("Cargando modelo Whisper small...")

        _modelo = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8"
        )

    return _modelo


def guardar_segmento(db, archivo_id, inicio, fin, texto):
    db.execute("""
        INSERT INTO transcripciones (
            archivo_id,
            inicio,
            fin,
            texto
        )
        VALUES (?, ?, ?, ?)
    """, (
        archivo_id,
        inicio,
        fin,
        texto.strip()
    ))


def transcribir_archivo(archivo_id, ruta):
    modelo = obtener_modelo()

    print()
    print("Transcribiendo:")
    print(ruta)

    segmentos, info = modelo.transcribe(
        ruta,
        language="es",
        beam_size=1
    )

    db = sqlite3.connect(DATABASE)

    cantidad = 0

    try:
        for segmento in segmentos:
            texto = segmento.text.strip()

            if not texto:
                continue

            guardar_segmento(
                db,
                archivo_id,
                segmento.start,
                segmento.end,
                texto
            )

            cantidad += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    print("Segmentos guardados:", cantidad)

    return cantidad