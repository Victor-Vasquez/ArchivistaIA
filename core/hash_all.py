import sqlite3
from pathlib import Path
import sys
import time

from core.hash import calcular_hash
from config.settings import DATABASE


def procesar_hashes():
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()

    cursor.execute("""
        SELECT id, ruta
        FROM archivos
        WHERE hash_archivo IS NULL
        ORDER BY id
    """)

    archivos = cursor.fetchall()
    total = len(archivos)

    print("=" * 60)
    print("CALCULO DE HASH SHA-256")
    print("=" * 60)
    print(f"Pendientes: {total}")
    print()

    procesados = 0
    errores = 0
    inicio = time.time()

    for id_archivo, ruta in archivos:

        try:
            hash_archivo = calcular_hash(ruta)

            cursor.execute("""
                UPDATE archivos
                SET hash_archivo = ?
                WHERE id = ?
            """, (hash_archivo, id_archivo))

            db.commit()

            procesados += 1

            if procesados % 10 == 0 or procesados == 1:
                transcurrido = time.time() - inicio
                velocidad = procesados / transcurrido if transcurrido else 0

                print(
                    f"Procesados: {procesados}/{total} | "
                    f"Errores: {errores} | "
                    f"Velocidad: {velocidad:.2f} archivos/s"
                )

        except Exception as e:

            errores += 1

            print(f"ERROR ID {id_archivo}: {ruta}")
            print(f"       {e}")

    db.close()

    print()
    print("=" * 60)
    print("PROCESO TERMINADO")
    print(f"Procesados: {procesados}")
    print(f"Errores:    {errores}")
    print("=" * 60)


if __name__ == "__main__":
    procesar_hashes()