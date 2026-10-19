import sqlite3
import time
import traceback
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

from faster_whisper import WhisperModel

from config.settings import DATABASE


FECHA_MINIMA = 1690848000  # 2023-08-01

_modelo = None


# Variantes que Whisper podría producir.
OBJETIVOS = [
    "celso",
    "celzo",
    "selso",
    "selsio",
    "celsio",
    "celcio",
    "ortiz",
    "ortis",
    "hortiz",
]


# Contexto que vuelve interesante un segmento,
# aunque Whisper destroce el nombre.
CONTEXTO = [
    "pastor",
    "hermano",
    "hermana",
    "obispo",
    "iglesia",
    "ministro",
    "presbitero",
    "presbítero",
    "reverendo",
    "superintendente",
]


def normalizar(texto):
    texto = texto.lower()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(
        c for c in texto
        if unicodedata.category(c) != "Mn"
    )

    return texto


def obtener_modelo():
    global _modelo

    if _modelo is None:
        print(
            "Cargando Whisper small "
            "para busqueda masiva..."
        )

        _modelo = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8",
        )

    return _modelo


def preparar_base():
    db = sqlite3.connect(DATABASE)

    db.execute("""
        CREATE TABLE IF NOT EXISTS busqueda_masiva (
            archivo_id INTEGER PRIMARY KEY,
            estado TEXT NOT NULL,
            segmentos INTEGER DEFAULT 0,
            sospechosos INTEGER DEFAULT 0,
            tiempo_segundos REAL,
            fecha_revision TEXT,
            error TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS hallazgos_masivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            archivo_id INTEGER NOT NULL,
            inicio REAL,
            fin REAL,
            texto TEXT,
            motivo TEXT,
            similitud REAL,
            fecha_registro TEXT
        )
    """)

    db.commit()
    db.close()


def similitud_palabra(palabra):
    mejor = 0.0
    objetivo_mejor = None

    for objetivo in OBJETIVOS:
        valor = SequenceMatcher(
            None,
            palabra,
            objetivo
        ).ratio()

        if valor > mejor:
            mejor = valor
            objetivo_mejor = objetivo

    return mejor, objetivo_mejor


def analizar_texto(texto):
    normal = normalizar(texto)

    palabras = (
        normal
        .replace(",", " ")
        .replace(".", " ")
        .replace(":", " ")
        .replace(";", " ")
        .replace("!", " ")
        .replace("?", " ")
        .split()
    )

    # Coincidencia textual directa.
    for objetivo in OBJETIVOS:
        if objetivo in normal:
            return (
                True,
                f"directa:{objetivo}",
                1.0
            )

    # Aproximación fonética/textual.
    for palabra in palabras:
        if len(palabra) < 4:
            continue

        similitud, objetivo = similitud_palabra(
            palabra
        )

        if similitud >= 0.72:
            return (
                True,
                f"aproximada:{palabra}->{objetivo}",
                similitud
            )

    # Contexto eclesiástico.
    #
    # Lo guardamos como sospechoso débil.
    # Después podremos buscar nombres alrededor
    # de estos segmentos sin repetir Whisper.
    for palabra in CONTEXTO:
        if normalizar(palabra) in normal:
            return (
                True,
                f"contexto:{palabra}",
                0.50
            )

    return False, None, 0.0


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
              FROM busqueda_masiva b
              WHERE b.archivo_id = a.id
                AND b.estado = 'COMPLETADO'
          )
        ORDER BY
            CAST(a.fecha_modificacion AS REAL) DESC
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
    sospechosos=0,
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
        INSERT OR REPLACE INTO busqueda_masiva (
            archivo_id,
            estado,
            segmentos,
            sospechosos,
            tiempo_segundos,
            fecha_revision,
            error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        archivo_id,
        estado,
        segmentos,
        sospechosos,
        tiempo_segundos,
        datetime.now().isoformat(),
        error,
    ))

    db.commit()
    db.close()


def guardar_hallazgo(
    archivo_id,
    inicio,
    fin,
    texto,
    motivo,
    similitud,
):
    db = sqlite3.connect(
        DATABASE,
        timeout=60
    )

    db.execute(
        "PRAGMA busy_timeout=60000"
    )

    db.execute("""
        INSERT INTO hallazgos_masivos (
            archivo_id,
            inicio,
            fin,
            texto,
            motivo,
            similitud,
            fecha_registro
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        archivo_id,
        inicio,
        fin,
        texto,
        motivo,
        similitud,
        datetime.now().isoformat(),
    ))

    db.commit()
    db.close()


def procesar_archivo(
    archivo_id,
    ruta
):
    modelo = obtener_modelo()

    print()
    print("Analizando:")
    print(ruta)

    segmentos, info = modelo.transcribe(
        ruta,
        language="es",
        beam_size=1,
        vad_filter=True,
        condition_on_previous_text=False,
    )

    total_segmentos = 0
    total_sospechosos = 0

    for segmento in segmentos:

        total_segmentos += 1

        texto = segmento.text.strip()

        if not texto:
            continue

        encontrado, motivo, similitud = (
            analizar_texto(texto)
        )

        if encontrado:

            total_sospechosos += 1

            guardar_hallazgo(
                archivo_id,
                segmento.start,
                segmento.end,
                texto,
                motivo,
                similitud,
            )

            print(
                f"[{segmento.start:.1f} - "
                f"{segmento.end:.1f}] "
                f"{motivo} | "
                f"{texto}"
            )

    return (
        total_segmentos,
        total_sospechosos
    )


def main():
    preparar_base()

    archivos = obtener_archivos()

    print("=" * 72)
    print("ARCHIVISTA IA - BUSQUEDA MASIVA")
    print("Whisper small")
    print("=" * 72)

    print(
        "Archivos pendientes:",
        len(archivos)
    )

    inicio_total = time.time()

    completados = 0
    errores = 0
    archivos_sospechosos = 0

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
            segmentos, sospechosos = (
                procesar_archivo(
                    archivo_id,
                    ruta
                )
            )

            duracion = (
                time.time() - inicio
            )

            guardar_estado(
                archivo_id,
                "COMPLETADO",
                segmentos,
                sospechosos,
                duracion,
            )

            completados += 1

            if sospechosos:
                archivos_sospechosos += 1

            print()
            print(
                f"Segmentos: {segmentos}"
            )

            print(
                f"Sospechosos: {sospechosos}"
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
                error=error
            )

            print()
            print(
                f"ERROR ID {archivo_id}"
            )

            print(error)

            traceback.print_exc()

            print(
                "Continuando..."
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
        "Archivos sospechosos:",
        archivos_sospechosos
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