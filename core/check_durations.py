import sqlite3
import subprocess

from config.settings import DATABASE


IDS_PRIORITARIOS = [
    192196,
    192200,
    192204,
    192206,
    192225,
    192230,
    192096,
]


def obtener_duracion(ruta):
    resultado = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            ruta,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if resultado.returncode != 0:
        return None, resultado.stderr.strip()

    try:
        segundos = float(resultado.stdout.strip())
        return segundos, None
    except ValueError:
        return None, "ffprobe no devolvió una duración válida"


def formatear_duracion(segundos):
    segundos = int(segundos)

    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    segundos = segundos % 60

    return f"{horas:02d}:{minutos:02d}:{segundos:02d}"


def main():
    db = sqlite3.connect(DATABASE)
    c = db.cursor()

    interrogantes = ",".join(
        "?" for _ in IDS_PRIORITARIOS
    )

    c.execute(
        f"""
        SELECT id, ruta
        FROM archivos
        WHERE id IN ({interrogantes})
        """,
        IDS_PRIORITARIOS,
    )

    archivos = c.fetchall()
    db.close()

    resultados = []

    for archivo_id, ruta in archivos:
        print(f"Revisando ID {archivo_id}...")

        duracion, error = obtener_duracion(ruta)

        if error:
            resultados.append(
                (archivo_id, None, ruta, error)
            )
        else:
            resultados.append(
                (archivo_id, duracion, ruta, None)
            )

    resultados.sort(
        key=lambda x: (
            x[1] is None,
            x[1] if x[1] is not None else 0
        )
    )

    print()
    print("=" * 70)
    print("CANDIDATOS ORDENADOS POR DURACION")
    print("=" * 70)

    for archivo_id, duracion, ruta, error in resultados:

        if error:
            print()
            print(f"ID {archivo_id} | ERROR")
            print(ruta)
            print(error)
            continue

        print()
        print(
            f"ID {archivo_id} | "
            f"{formatear_duracion(duracion)}"
        )
        print(ruta)


if __name__ == "__main__":
    main()