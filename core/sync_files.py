from pathlib import Path
import hashlib
import sqlite3
import time

from config.settings import DATABASE


ROOT = Path("E:/")

EXTENSIONES_AUDIO = {
    ".mp3", ".wav", ".m4a", ".aac",
    ".flac", ".ogg", ".wma", ".opus",
}

EXTENSIONES_VIDEO = {
    ".mp4", ".mov", ".avi", ".mkv",
    ".mpg", ".mpeg", ".wmv", ".m4v",
    ".webm", ".mts", ".m2ts", ".vob",
}


def tipo_archivo(ruta: Path):
    ext = ruta.suffix.lower()

    if ext in EXTENSIONES_AUDIO:
        return "AUDIO"

    if ext in EXTENSIONES_VIDEO:
        return "VIDEO"

    return "OTRO"


def asegurar_columna(db):
    columnas = {
        fila[1]
        for fila in db.execute(
            "PRAGMA table_info(archivos)"
        )
    }

    if "existe" not in columnas:
        print("Agregando columna existe...")

        db.execute("""
            ALTER TABLE archivos
            ADD COLUMN existe INTEGER DEFAULT 1
        """)

        db.commit()


def main():

    if not ROOT.exists():
        raise RuntimeError(
            f"No está disponible el disco {ROOT}"
        )

    db = sqlite3.connect(
        DATABASE,
        timeout=60
    )

    db.execute(
        "PRAGMA busy_timeout=60000"
    )

    asegurar_columna(db)

    # ---------------------------------------------------
    # Todas las rutas conocidas
    # ---------------------------------------------------

    existentes_db = {
        ruta: archivo_id
        for archivo_id, ruta
        in db.execute("""
            SELECT id, ruta
            FROM archivos
        """)
    }

    print(
        "Registros actuales:",
        len(existentes_db)
    )

    # Primero asumimos que ninguno existe.
    # Los que encontremos durante el escaneo
    # volverán a quedar en 1.
    db.execute("""
        UPDATE archivos
        SET existe = 0
    """)

    db.commit()

    encontrados = 0
    nuevos = 0
    actualizados = 0
    errores = 0

    inicio = time.time()

    print()
    print("Escaneando E:\\ ...")
    print()

    for ruta in ROOT.rglob("*"):

        try:
            if not ruta.is_file():
                continue

            encontrados += 1

            ruta_str = str(ruta)

            stat = ruta.stat()

            fecha_modificacion = (
                stat.st_mtime
            )

            tamano = stat.st_size

            tipo = tipo_archivo(ruta)

            if ruta_str in existentes_db:

                db.execute("""
                    UPDATE archivos
                    SET
                        existe = 1,
                        fecha_modificacion = ?,
                        tipo = ?
                    WHERE id = ?
                """, (
                    fecha_modificacion,
                    tipo,
                    existentes_db[ruta_str],
                ))

                actualizados += 1

            else:

                # Primero vemos qué columnas existen
                # para no depender de una versión
                # particular del esquema.
                columnas = {
                    fila[1]
                    for fila in db.execute(
                        "PRAGMA table_info(archivos)"
                    )
                }

                if "tamano" in columnas:

                    db.execute("""
                        INSERT INTO archivos (
                            ruta,
                            tipo,
                            tamano,
                            fecha_modificacion,
                            existe
                        )
                        VALUES (?, ?, ?, ?, 1)
                    """, (
                        ruta_str,
                        tipo,
                        tamano,
                        fecha_modificacion,
                    ))

                else:

                    db.execute("""
                        INSERT INTO archivos (
                            ruta,
                            tipo,
                            fecha_modificacion,
                            existe
                        )
                        VALUES (?, ?, ?, 1)
                    """, (
                        ruta_str,
                        tipo,
                        fecha_modificacion,
                    ))

                nuevos += 1

            if encontrados % 1000 == 0:

                db.commit()

                transcurrido = (
                    time.time() - inicio
                )

                print(
                    f"{encontrados:,} archivos | "
                    f"nuevos {nuevos:,} | "
                    f"{transcurrido / 60:.1f} min"
                )

        except Exception as e:

            errores += 1

            print()
            print(
                "ERROR:",
                ruta
            )
            print(e)

    db.commit()

    desaparecidos = db.execute("""
        SELECT COUNT(*)
        FROM archivos
        WHERE existe = 0
    """).fetchone()[0]

    activos = db.execute("""
        SELECT COUNT(*)
        FROM archivos
        WHERE existe = 1
    """).fetchone()[0]

    db.close()

    duracion = (
        time.time() - inicio
    )

    print()
    print("=" * 72)
    print("SINCRONIZACION TERMINADA")
    print("=" * 72)

    print(
        f"Archivos encontrados: {encontrados:,}"
    )

    print(
        f"Archivos nuevos:      {nuevos:,}"
    )

    print(
        f"Actualizados:          {actualizados:,}"
    )

    print(
        f"Ya no existen:        {desaparecidos:,}"
    )

    print(
        f"Activos en índice:     {activos:,}"
    )

    print(
        f"Errores:               {errores:,}"
    )

    print(
        f"Tiempo:                "
        f"{duracion / 60:.1f} minutos"
    )


if __name__ == "__main__":
    main()