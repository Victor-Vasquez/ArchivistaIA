import sqlite3
import time

from config.settings import DATABASE
from core.transcriber import transcribir_archivo


LIMITE = 3


def obtener_pendientes():
    db = sqlite3.connect(DATABASE)
    c = db.cursor()

    c.execute("""
        SELECT
            a.id,
            a.ruta,
            a.tipo
        FROM archivos a
        WHERE a.tipo IN ('AUDIO', 'VIDEO')
          AND NOT EXISTS (
              SELECT 1
              FROM transcripciones t
              WHERE t.archivo_id = a.id
          )
        ORDER BY a.id
    """)

    resultados = c.fetchall()

    db.close()

    return resultados


def procesar_pendientes():
    pendientes = obtener_pendientes()

    print("Archivos multimedia pendientes:", len(pendientes))
    print("Procesaremos ahora:", min(LIMITE, len(pendientes)))
    print()

    inicio = time.time()
    procesados = 0
    errores = 0

    for archivo_id, ruta, tipo in pendientes[:LIMITE]:
        print("=" * 60)
        print(f"ID: {archivo_id}")
        print(f"Tipo: {tipo}")
        print(f"Ruta: {ruta}")

        try:
            cantidad = transcribir_archivo(
                archivo_id,
                ruta
            )

            procesados += 1

            print(
                f"OK - Segmentos guardados: {cantidad}"
            )

        except Exception as e:
            errores += 1

            print(
                f"ERROR ID {archivo_id}: "
                f"{type(e).__name__}: {e}"
            )

    transcurrido = time.time() - inicio

    print()
    print("=" * 60)
    print("PRUEBA TERMINADA")
    print(f"Procesados correctamente: {procesados}")
    print(f"Errores: {errores}")
    print(f"Tiempo total: {transcurrido:.2f} segundos")
    print("=" * 60)


if __name__ == "__main__":
    procesar_pendientes()