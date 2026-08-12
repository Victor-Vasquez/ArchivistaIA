import sqlite3
import time
import traceback
from datetime import datetime

from config.settings import DATABASE
from core.detect_mentions import detectar_menciones


# 1 de agosto de 2023, aproximadamente
FECHA_MINIMA = 1690848000

PALABRAS_RELEVANTES = [
    "iglesia",
    "pastor",
    "mensaje",
    "estudio",
    "biblico",
    "bíblico",
    "conferencia",
    "predic",
    "devocional",
    "confraternidad",
    "culto",
    "aniversario",
    "consagracion",
    "consagración",
    "visita",
    "maipo",
    "peñaflor",
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


def ruta_relevante(ruta):
    ruta = ruta.lower()

    return any(
        palabra in ruta
        for palabra in PALABRAS_RELEVANTES
    )


def obtener_candidatos():
    db = sqlite3.connect(DATABASE)
    c = db.cursor()

    c.execute("""
        SELECT
            id,
            ruta,
            tipo,
            hash_archivo,
            CAST(fecha_modificacion AS REAL)
        FROM archivos
        WHERE tipo IN ('AUDIO', 'VIDEO')
          AND CAST(fecha_modificacion AS REAL) >= ?
        ORDER BY CAST(fecha_modificacion AS REAL) DESC
    """, (FECHA_MINIMA,))

    archivos = c.fetchall()

    # Hashes ya representados por otro archivo.
    hashes_vistos = set()

    candidatos = []

    for (
        archivo_id,
        ruta,
        tipo,
        hash_archivo,
        fecha_modificacion
    ) in archivos:

        if not ruta_relevante(ruta):
            continue

        # Si ya terminó anteriormente, no repetir.
        c.execute("""
            SELECT estado
            FROM deteccion_menciones
            WHERE archivo_id = ?
        """, (archivo_id,))

        registro = c.fetchone()

        if registro and registro[0] == "COMPLETADO":
            continue

        # Deduplicación real por SHA-256.
        if hash_archivo:
            if hash_archivo in hashes_vistos:
                continue

            hashes_vistos.add(hash_archivo)

        candidatos.append(
            (
                archivo_id,
                ruta,
                tipo,
                fecha_modificacion
            )
        )

    db.close()

    return candidatos


def guardar_estado(
    archivo_id,
    estado,
    coincidencias=0,
    tiempo_segundos=None,
    error=None
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
        error
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

    # Evita duplicarlas si alguna vez
    # reprocesamos el archivo.
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
            datetime.now().isoformat()
        ))

    db.commit()
    db.close()


def main():
    preparar_base()

    candidatos = obtener_candidatos()

    print("=" * 70)
    print("ARCHIVISTA IA")
    print("BUSQUEDA RECIENTE DE CELSO ORTIZ")
    print("=" * 70)

    print(
        "Candidatos recientes y relevantes:",
        len(candidatos)
    )

    print()

    if not candidatos:
        print("No quedan candidatos pendientes.")
        return

    inicio_total = time.time()

    completados = 0
    positivos = 0
    errores = 0

    for numero, (
        archivo_id,
        ruta,
        tipo,
        fecha_modificacion
    ) in enumerate(candidatos, 1):

        print()
        print("#" * 70)

        print(
            f"ARCHIVO {numero}/"
            f"{len(candidatos)}"
        )

        print(f"ID: {archivo_id}")
        print(f"Tipo: {tipo}")
        print(f"Ruta: {ruta}")

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
                time.time() -
                inicio_archivo
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
                None
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
                "minutos"
            )

        except KeyboardInterrupt:

            tiempo_archivo = (
                time.time() -
                inicio_archivo
            )

            guardar_estado(
                archivo_id,
                "INTERRUMPIDO",
                0,
                tiempo_archivo,
                "Interrumpido"
            )

            print()
            print(
                "Proceso interrumpido."
            )

            break

        except Exception as e:

            tiempo_archivo = (
                time.time() -
                inicio_archivo
            )

            error_texto = (
                f"{type(e).__name__}: {e}"
            )

            guardar_estado(
                archivo_id,
                "ERROR",
                0,
                tiempo_archivo,
                error_texto
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
                "el siguiente archivo..."
            )

    tiempo_total = (
        time.time() -
        inicio_total
    )

    print()
    print("=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)

    print(
        "Completados:",
        completados
    )

    print(
        "Positivos:",
        positivos
    )

    print(
        "Errores:",
        errores
    )

    print(
        "Tiempo total:",
        f"{tiempo_total / 3600:.2f}",
        "horas"
    )


if __name__ == "__main__":
    main()