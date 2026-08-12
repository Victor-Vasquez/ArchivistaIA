import sqlite3
from datetime import datetime

from config.settings import DATABASE


FECHA_MINIMA = 1690848000


def numero(valor):
    return f"{valor:,}".replace(",", ".")


def fecha_legible(fecha):
    if not fecha:
        return "-"

    try:
        return datetime.fromisoformat(fecha).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except Exception:
        return fecha


def main():
    db = sqlite3.connect(
        DATABASE,
        timeout=30
    )

    db.execute(
        "PRAGMA busy_timeout=30000"
    )

    c = db.cursor()

    # ---------------------------------------------------------
    # ARCHIVOS
    # ---------------------------------------------------------

    total = c.execute("""
        SELECT COUNT(*)
        FROM archivos
    """).fetchone()[0]

    multimedia = c.execute("""
        SELECT COUNT(*)
        FROM archivos
        WHERE tipo IN ('AUDIO', 'VIDEO')
    """).fetchone()[0]

    audio = c.execute("""
        SELECT COUNT(*)
        FROM archivos
        WHERE tipo = 'AUDIO'
    """).fetchone()[0]

    video = c.execute("""
        SELECT COUNT(*)
        FROM archivos
        WHERE tipo = 'VIDEO'
    """).fetchone()[0]

    con_hash = c.execute("""
        SELECT COUNT(*)
        FROM archivos
        WHERE hash_archivo IS NOT NULL
    """).fetchone()[0]

    sin_hash = total - con_hash

    recientes = c.execute("""
        SELECT COUNT(*)
        FROM archivos
        WHERE tipo IN ('AUDIO', 'VIDEO')
          AND CAST(fecha_modificacion AS REAL) >= ?
    """, (FECHA_MINIMA,)).fetchone()[0]

    # ---------------------------------------------------------
    # DETECCION
    # ---------------------------------------------------------

    try:
        estados = dict(
            c.execute("""
                SELECT estado, COUNT(*)
                FROM deteccion_menciones
                GROUP BY estado
            """).fetchall()
        )

        positivos = c.execute("""
            SELECT COUNT(*)
            FROM deteccion_menciones
            WHERE coincidencias > 0
        """).fetchone()[0]

        total_revisados = c.execute("""
            SELECT COUNT(*)
            FROM deteccion_menciones
        """).fetchone()[0]

        recientes_completados = c.execute("""
            SELECT COUNT(*)
            FROM deteccion_menciones d
            JOIN archivos a
                ON a.id = d.archivo_id
            WHERE d.estado = 'COMPLETADO'
              AND a.tipo IN ('AUDIO', 'VIDEO')
              AND CAST(a.fecha_modificacion AS REAL) >= ?
        """, (FECHA_MINIMA,)).fetchone()[0]

        pendientes_recientes = max(
            0,
            recientes - recientes_completados
        )

        ultimos = c.execute("""
            SELECT
                d.archivo_id,
                d.estado,
                d.coincidencias,
                d.tiempo_segundos,
                d.fecha_revision,
                a.ruta
            FROM deteccion_menciones d
            JOIN archivos a
                ON a.id = d.archivo_id
            ORDER BY d.fecha_revision DESC
            LIMIT 10
        """).fetchall()

    except sqlite3.OperationalError:
        estados = {}
        positivos = 0
        total_revisados = 0
        recientes_completados = 0
        pendientes_recientes = recientes
        ultimos = []

    db.close()

    # ---------------------------------------------------------
    # INFORME
    # ---------------------------------------------------------

    print()
    print("=" * 72)
    print("ARCHIVISTA IA - ESTADO")
    print("=" * 72)

    print()
    print("ARCHIVO GENERAL")
    print("-" * 72)

    print(
        f"Archivos indexados:       {numero(total):>12}"
    )

    print(
        f"Multimedia:               {numero(multimedia):>12}"
    )

    print(
        f"  Audio:                  {numero(audio):>12}"
    )

    print(
        f"  Video:                  {numero(video):>12}"
    )

    print(
        f"Con hash SHA-256:         {numero(con_hash):>12}"
    )

    print(
        f"Sin hash:                 {numero(sin_hash):>12}"
    )

    print()
    print("BUSQUEDA RECIENTE")
    print("-" * 72)

    print(
        f"Multimedia desde 08/2023: {numero(recientes):>12}"
    )

    print(
        f"Recientes completados:    "
        f"{numero(recientes_completados):>12}"
    )

    print(
        f"Recientes pendientes:     "
        f"{numero(pendientes_recientes):>12}"
    )

    print()
    print("DETECCION DE MENCIONES")
    print("-" * 72)

    print(
        f"Registros de deteccion:   "
        f"{numero(total_revisados):>12}"
    )

    print(
        f"Completados:              "
        f"{numero(estados.get('COMPLETADO', 0)):>12}"
    )

    print(
        f"Procesando:               "
        f"{numero(estados.get('PROCESANDO', 0)):>12}"
    )

    print(
        f"Interrumpidos:            "
        f"{numero(estados.get('INTERRUMPIDO', 0)):>12}"
    )

    print(
        f"Errores:                  "
        f"{numero(estados.get('ERROR', 0)):>12}"
    )

    print(
        f"Archivos con coincidencia:"
        f"{numero(positivos):>13}"
    )

    print()
    print("ULTIMOS ARCHIVOS REGISTRADOS")
    print("-" * 72)

    if not ultimos:
        print("Sin registros.")

    for (
        archivo_id,
        estado,
        coincidencias,
        tiempo_segundos,
        fecha_revision,
        ruta,
    ) in ultimos:

        if tiempo_segundos:
            minutos = tiempo_segundos / 60
            tiempo = f"{minutos:.1f} min"
        else:
            tiempo = "-"

        print()
        print(
            f"ID {archivo_id} | "
            f"{estado} | "
            f"Coincidencias: {coincidencias} | "
            f"{tiempo}"
        )

        print(
            f"Fecha: {fecha_legible(fecha_revision)}"
        )

        print(ruta)

    print()
    print("=" * 72)


if __name__ == "__main__":
    main()