import sqlite3
import time

from core.hash import calcular_hash
from config.settings import DATABASE


MAX_REINTENTOS = 10
ESPERA_REINTENTO = 2


def guardar_hash(db, cursor, id_archivo, hash_archivo):
    """
    Guarda un hash en SQLite.
    Si la base está temporalmente bloqueada, espera y reintenta.
    """

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            cursor.execute(
                """
                UPDATE archivos
                SET hash_archivo = ?
                WHERE id = ?
                """,
                (hash_archivo, id_archivo)
            )

            db.commit()
            return True

        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower():
                raise

            db.rollback()

            print(
                f"Base ocupada. Reintento "
                f"{intento}/{MAX_REINTENTOS}..."
            )

            time.sleep(ESPERA_REINTENTO)

    return False


def procesar_hashes():
    db = sqlite3.connect(
        DATABASE,
        timeout=60
    )

    db.execute("PRAGMA busy_timeout = 60000")

    cursor = db.cursor()

    cursor.execute(
        """
        SELECT id, ruta
        FROM archivos
        WHERE hash_archivo IS NULL
        ORDER BY id
        """
    )

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
            # El archivo se lee una sola vez.
            hash_archivo = calcular_hash(ruta)

            guardado = guardar_hash(
                db,
                cursor,
                id_archivo,
                hash_archivo
            )

            if not guardado:
                errores += 1

                print(
                    f"ERROR ID {id_archivo}: {ruta}"
                )
                print(
                    "       No fue posible guardar "
                    "después de varios reintentos."
                )

                continue

            procesados += 1

            if procesados % 10 == 0 or procesados == 1:
                transcurrido = time.time() - inicio

                velocidad = (
                    procesados / transcurrido
                    if transcurrido
                    else 0
                )

                print(
                    f"Procesados: {procesados}/{total} | "
                    f"Errores: {errores} | "
                    f"Velocidad: {velocidad:.2f} archivos/s"
                )

        except FileNotFoundError:
            errores += 1

            print(f"ARCHIVO NO ENCONTRADO ID {id_archivo}:")
            print(f"       {ruta}")

        except PermissionError:
            errores += 1

            print(f"SIN PERMISO ID {id_archivo}:")
            print(f"       {ruta}")

        except Exception as e:
            errores += 1

            print(f"ERROR ID {id_archivo}: {ruta}")
            print(f"       {type(e).__name__}: {e}")

    db.close()

    print()
    print("=" * 60)
    print("PROCESO TERMINADO")
    print(f"Procesados: {procesados}")
    print(f"Errores:    {errores}")
    print("=" * 60)


if __name__ == "__main__":
    procesar_hashes()