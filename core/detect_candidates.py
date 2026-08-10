import sqlite3
import time
import traceback

from datetime import datetime

from config.settings import DATABASE
from core.detect_mentions import detectar_menciones


IDS = [
    192230,
    192204,
    192096,
    192225,
    192196,
    192200,
    192206,
]


def obtener_archivos():
    db = sqlite3.connect(DATABASE)
    c = db.cursor()

    interrogantes = ",".join("?" for _ in IDS)

    c.execute(
        f"""
        SELECT
            a.id,
            a.ruta
        FROM archivos a
        WHERE a.id IN ({interrogantes})
          AND NOT EXISTS (
              SELECT 1
              FROM deteccion_menciones d
              WHERE d.archivo_id = a.id
                AND d.estado = 'COMPLETADO'
          )
        """,
        IDS,
    )

    encontrados = {
        archivo_id: ruta
        for archivo_id, ruta in c.fetchall()
    }

    db.close()

    return [
        (archivo_id, encontrados[archivo_id])
        for archivo_id in IDS
        if archivo_id in encontrados
    ]


def guardar_resultado(
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
        "PRAGMA busy_timeout = 60000"
    )

    db.execute(
        """
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
        """,
        (
            archivo_id,
            "medium",
            estado,
            coincidencias,
            tiempo_segundos,
            datetime.now().isoformat(),
            error,
        ),
    )

    db.commit()
    db.close()


def main():
    archivos = obtener_archivos()

    print("=" * 70)
    print(
        "BUSQUEDA DE CELSO ORTIZ - "
        "CANDIDATOS PRIORITARIOS"
    )
    print("=" * 70)
    print(
        f"Archivos pendientes: "
        f"{len(archivos)}"
    )
    print()

    if not archivos:
        print(
            "No quedan candidatos pendientes."
        )
        return

    inicio_total = time.time()

    positivos = []
    errores = []

    for numero, (archivo_id, ruta) in enumerate(
        archivos,
        1
    ):
        print()
        print("#" * 70)
        print(
            f"ARCHIVO {numero}/"
            f"{len(archivos)}"
        )
        print(f"ID: {archivo_id}")
        print(ruta)
        print("#" * 70)

        inicio_archivo = time.time()

        try:
            coincidencias = detectar_menciones(
                ruta
            )

            duracion = (
                time.time() - inicio_archivo
            )

            guardar_resultado(
                archivo_id=archivo_id,
                estado="COMPLETADO",
                coincidencias=len(
                    coincidencias
                ),
                tiempo_segundos=duracion,
                error=None,
            )

            if coincidencias:
                positivos.append(
                    (
                        archivo_id,
                        ruta,
                        coincidencias,
                        duracion,
                    )
                )

                print()
                print(
                    "*** POSIBLE COINCIDENCIA "
                    "ENCONTRADA ***"
                )
                print(
                    f"Cantidad: "
                    f"{len(coincidencias)}"
                )

            else:
                print()
                print(
                    "Sin coincidencias."
                )

            print(
                f"Tiempo archivo: "
                f"{duracion / 60:.1f} "
                f"minutos"
            )

        except KeyboardInterrupt:
            duracion = (
                time.time() - inicio_archivo
            )

            guardar_resultado(
                archivo_id=archivo_id,
                estado="INTERRUMPIDO",
                coincidencias=0,
                tiempo_segundos=duracion,
                error=(
                    "Interrumpido por el usuario"
                ),
            )

            print()
            print(
                "Proceso interrumpido "
                "por el usuario."
            )

            break

        except Exception as e:
            duracion = (
                time.time() - inicio_archivo
            )

            error_texto = (
                f"{type(e).__name__}: {e}"
            )

            guardar_resultado(
                archivo_id=archivo_id,
                estado="ERROR",
                coincidencias=0,
                tiempo_segundos=duracion,
                error=error_texto,
            )

            errores.append(
                (
                    archivo_id,
                    ruta,
                    error_texto,
                )
            )

            print()
            print(
                f"ERROR EN ID "
                f"{archivo_id}"
            )
            print(error_texto)

            traceback.print_exc()

            print()
            print(
                "Continuando con el "
                "siguiente archivo..."
            )

    tiempo_total = (
        time.time() - inicio_total
    )

    print()
    print("=" * 70)
    print("RESUMEN FINAL")
    print("=" * 70)

    print(
        f"Positivos: {len(positivos)}"
    )
    print(
        f"Errores:   {len(errores)}"
    )
    print(
        f"Tiempo total: "
        f"{tiempo_total / 3600:.2f} "
        f"horas"
    )

    if positivos:
        print()
        print(
            "POSIBLES COINCIDENCIAS:"
        )

        for (
            archivo_id,
            ruta,
            coincidencias,
            duracion,
        ) in positivos:

            print()
            print(
                f"ID {archivo_id}"
            )
            print(ruta)

            for coincidencia in coincidencias:
                print(
                    f"  "
                    f"["
                    f"{coincidencia['inicio']:.1f}"
                    f" - "
                    f"{coincidencia['fin']:.1f}"
                    f"] "
                    f"{coincidencia['texto']}"
                )

    if errores:
        print()
        print(
            "ARCHIVOS CON ERROR:"
        )

        for (
            archivo_id,
            ruta,
            error,
        ) in errores:

            print()
            print(
                f"ID {archivo_id}"
            )
            print(ruta)
            print(error)


if __name__ == "__main__":
    main()