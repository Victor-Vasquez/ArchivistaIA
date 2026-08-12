import sqlite3
import subprocess
import time
import traceback
from datetime import datetime

from config.settings import DATABASE
from core.detect_mentions import detectar_menciones


# 1 agosto 2023
FECHA_MINIMA = 1690848000

# Cantidad máxima para esta tanda nocturna.
LIMITE = 25

# Cosas que claramente no nos interesan.
EXCLUIR = [
    "jdownloader",
    "captcha.wav",
    "salesforce",
    "curso",
    "performance",
    "ted ",
    "ringtone",
    "rigntone",
    "incrediblemail",
    "corel",
    "grabación de llamada",
    "grabacion de llamada",
    "organizaciondeltiempo",
    "organizacion del tiempo",
]

# Elementos que aumentan mucho la prioridad.
PRIORIZAR = [
    "iglesia",
    "pastor",
    "mensaje",
    "estudio",
    "bíblico",
    "biblico",
    "confraternidad",
    "peñaflor",
    "maipo",
    "visita",
    "culto",
    "devocional",
    "conferencia",
    "predic",
    "templo",
    "hermano",
    "hno",
    "obispo",
    "reunion",
    "reunión",
    "servicio",
    "predica",
    "prédica",
    "predicación",
    "predicacion",
    "evangelico",
    "evangélico",
]


def preparar_base():
    db = sqlite3.connect(DATABASE)

    db.execute("""
        CREATE TABLE IF NOT EXISTS deteccion_menciones (
            archivo_id INTEGER PRIMARY KEY,
            modelo TEXT NOT NULL,
            estado TEXT NOT NULL,
            coincidencias INTEGER DEFAULT 0,
            tiempo_segundos REAL,
            fecha_revision TEXT,
            error TEXT,
            FOREIGN KEY (archivo_id)
                REFERENCES archivos(id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS deteccion_coincidencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            archivo_id INTEGER NOT NULL,
            inicio REAL,
            fin REAL,
            texto TEXT,
            fecha_registro TEXT,
            FOREIGN KEY (archivo_id)
                REFERENCES archivos(id)
        )
    """)

    db.commit()
    db.close()


def obtener_duracion(ruta):
    try:
        resultado = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                ruta,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )

        if resultado.returncode != 0:
            return None

        return float(resultado.stdout.strip())

    except Exception:
        return None


def puntaje_ruta(ruta):
    ruta_lower = ruta.lower()

    if any(
        palabra in ruta_lower
        for palabra in EXCLUIR
    ):
        return -1000

    puntaje = 0

    for palabra in PRIORIZAR:
        if palabra in ruta_lower:
            puntaje += 10

    # Preferimos archivos que parecen grabaciones
    # personales sobre material descargado genérico.
    if "dcim" in ruta_lower:
        puntaje += 3

    if "voice recorder" in ruta_lower:
        puntaje += 5

    if "download" in ruta_lower:
        puntaje += 1

    if "2024" in ruta_lower:
        puntaje += 2

    if "2025" in ruta_lower:
        puntaje += 2

    if "2026" in ruta_lower:
        puntaje += 2

    return puntaje


def obtener_candidatos():
    db = sqlite3.connect(DATABASE)
    c = db.cursor()

    c.execute("""
        SELECT
            a.id,
            a.ruta,
            a.tipo,
            a.hash_archivo,
            CAST(a.fecha_modificacion AS REAL)
        FROM archivos a
        WHERE a.tipo IN ('AUDIO', 'VIDEO')
          AND CAST(a.fecha_modificacion AS REAL) >= ?
          AND NOT EXISTS (
              SELECT 1
              FROM deteccion_menciones d
              WHERE d.archivo_id = a.id
                AND d.estado = 'COMPLETADO'
          )
        ORDER BY CAST(a.fecha_modificacion AS REAL) DESC
    """, (FECHA_MINIMA,))

    archivos = c.fetchall()
    db.close()

    hashes_vistos = set()
    candidatos = []

    print(
        "Archivos recientes todavía no revisados:",
        len(archivos)
    )
    print()
    print("Midiendo y priorizando candidatos...")
    print()

    for (
        archivo_id,
        ruta,
        tipo,
        hash_archivo,
        fecha_modificacion
    ) in archivos:

        puntaje = puntaje_ruta(ruta)

        if puntaje < 0:
            continue

        if hash_archivo:
            if hash_archivo in hashes_vistos:
                continue

            hashes_vistos.add(hash_archivo)

        duracion = obtener_duracion(ruta)

        if duracion is None:
            continue

        # Evitamos sonidos diminutos y archivos accidentales.
        if duracion < 20:
            continue

        candidatos.append(
            {
                "id": archivo_id,
                "ruta": ruta,
                "tipo": tipo,
                "fecha": fecha_modificacion,
                "duracion": duracion,
                "puntaje": puntaje,
            }
        )

    # Primero mayor relevancia.
    # A igualdad de relevancia, primero el más corto.
    candidatos.sort(
        key=lambda x: (
            -x["puntaje"],
            x["duracion"],
        )
    )

    return candidatos[:LIMITE]


def guardar_estado(
    archivo_id,
    estado,
    coincidencias=0,
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
        INSERT OR REPLACE INTO deteccion_menciones (
            archivo_id,
            modelo,
            estado,
            coincidencias,
            tiempo_segundos,
            fecha_revision,
            error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        archivo_id,
        "medium",
        estado,
        coincidencias,
        tiempo_segundos,
        datetime.now().isoformat(),
        error,
    ))

    db.commit()
    db.close()


def guardar_coincidencias(
    archivo_id,
    coincidencias
):
    db = sqlite3.connect(
        DATABASE,
        timeout=60
    )

    db.execute(
        "PRAGMA busy_timeout=60000"
    )

    db.execute("""
        DELETE FROM deteccion_coincidencias
        WHERE archivo_id = ?
    """, (archivo_id,))

    for coincidencia in coincidencias:
        db.execute("""
            INSERT INTO deteccion_coincidencias (
                archivo_id,
                inicio,
                fin,
                texto,
                fecha_registro
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            archivo_id,
            coincidencia["inicio"],
            coincidencia["fin"],
            coincidencia["texto"],
            datetime.now().isoformat(),
        ))

    db.commit()
    db.close()


def formatear_duracion(segundos):
    segundos = int(segundos)

    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    segundos = segundos % 60

    return (
        f"{horas:02d}:"
        f"{minutos:02d}:"
        f"{segundos:02d}"
    )


def main():
    preparar_base()

    candidatos = obtener_candidatos()

    print()
    print("=" * 70)
    print("ARCHIVISTA IA")
    print("BUSQUEDA AMPLIADA RECIENTE DE CELSO ORTIZ")
    print("=" * 70)

    print(
        "Candidatos seleccionados:",
        len(candidatos)
    )

    print()

    for candidato in candidatos:
        print(
            f"ID {candidato['id']} | "
            f"Puntaje {candidato['puntaje']} | "
            f"{formatear_duracion(candidato['duracion'])}"
        )
        print(candidato["ruta"])

    if not candidatos:
        print()
        print("No quedan candidatos para esta tanda.")
        return

    inicio_total = time.time()

    completados = 0
    positivos = 0
    errores = 0

    for numero, candidato in enumerate(
        candidatos,
        1
    ):
        archivo_id = candidato["id"]
        ruta = candidato["ruta"]

        print()
        print("#" * 70)
        print(
            f"ARCHIVO {numero}/"
            f"{len(candidatos)}"
        )
        print(f"ID: {archivo_id}")
        print(
            "Duracion:",
            formatear_duracion(
                candidato["duracion"]
            )
        )
        print(
            "Puntaje:",
            candidato["puntaje"]
        )
        print(ruta)
        print("#" * 70)

        inicio_archivo = time.time()

        guardar_estado(
            archivo_id,
            "PROCESANDO"
        )

        try:
            coincidencias = detectar_menciones(
                ruta
            )

            tiempo_archivo = (
                time.time()
                - inicio_archivo
            )

            guardar_coincidencias(
                archivo_id,
                coincidencias
            )

            guardar_estado(
                archivo_id,
                "COMPLETADO",
                len(coincidencias),
                tiempo_archivo,
                None,
            )

            completados += 1

            if coincidencias:
                positivos += 1

                print()
                print(
                    "!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                )
                print(
                    "POSIBLE CELSO ORTIZ ENCONTRADO"
                )
                print(
                    "!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                )

                for coincidencia in coincidencias:
                    print(
                        f"["
                        f"{coincidencia['inicio']:.1f}"
                        f" - "
                        f"{coincidencia['fin']:.1f}"
                        f"] "
                        f"{coincidencia['texto']}"
                    )

            else:
                print()
                print(
                    "Sin coincidencias."
                )

            print(
                "Tiempo archivo:",
                f"{tiempo_archivo / 60:.1f}",
                "minutos",
            )

        except KeyboardInterrupt:
            tiempo_archivo = (
                time.time()
                - inicio_archivo
            )

            guardar_estado(
                archivo_id,
                "INTERRUMPIDO",
                0,
                tiempo_archivo,
                "Interrumpido",
            )

            print()
            print("Proceso interrumpido.")
            break

        except Exception as e:
            tiempo_archivo = (
                time.time()
                - inicio_archivo
            )

            error_texto = (
                f"{type(e).__name__}: {e}"
            )

            guardar_estado(
                archivo_id,
                "ERROR",
                0,
                tiempo_archivo,
                error_texto,
            )

            errores += 1

            print()
            print(
                f"ERROR ID {archivo_id}"
            )
            print(error_texto)

            traceback.print_exc()

            print()
            print(
                "Continuando con "
                "el siguiente..."
            )

    tiempo_total = (
        time.time()
        - inicio_total
    )

    print()
    print("=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)

    print("Completados:", completados)
    print("Positivos:", positivos)
    print("Errores:", errores)

    print(
        "Tiempo total:",
        f"{tiempo_total / 3600:.2f}",
        "horas",
    )


if __name__ == "__main__":
    main()