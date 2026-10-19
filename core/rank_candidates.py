import sqlite3
import subprocess
from datetime import datetime

from config.settings import DATABASE


FECHA_MINIMA = 1690848000  # 2023-08-01


PALABRAS = {
    # Muy fuertes
    "celso": 100,
    "ortiz": 100,
    "pastor": 40,
    "obispo": 40,

    # Contexto religioso fuerte
    "iglesia": 30,
    "culto": 30,
    "predic": 30,
    "devocional": 30,
    "conferencia": 25,
    "confraternidad": 25,
    "biblico": 25,
    "bíblico": 25,
    "estudio": 20,
    "mensaje": 20,

    # Contexto potencial
    "servicio": 15,
    "reunion": 15,
    "reunión": 15,
    "visita": 15,
    "templo": 15,
    "hermano": 10,
    "hno": 10,
    "maipu": 10,
    "maipú": 10,
    "peñaflor": 10,
}


PENALIZAR = {
    "telegram": -10,
    "whatsapp": -5,
    "download": -5,
    "y2meta": -50,
    "youtube": -40,
    "curso": -40,
    "salesforce": -100,
    "jdownloader": -100,
    "__no_incluir__": -100,
}


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
            timeout=30,
        )

        if resultado.returncode != 0:
            return None

        return float(resultado.stdout.strip())

    except Exception:
        return None


def calcular_puntaje(ruta):
    texto = ruta.lower()

    puntaje = 0
    motivos = []

    for palabra, valor in PALABRAS.items():
        if palabra in texto:
            puntaje += valor
            motivos.append(f"{palabra}:+{valor}")

    for palabra, valor in PENALIZAR.items():
        if palabra in texto:
            puntaje += valor
            motivos.append(f"{palabra}:{valor}")

    return puntaje, motivos


def formatear_duracion(segundos):
    if segundos is None:
        return "??:??:??"

    segundos = int(segundos)

    h = segundos // 3600
    m = (segundos % 3600) // 60
    s = segundos % 60

    return f"{h:02d}:{m:02d}:{s:02d}"


def main():

    db = sqlite3.connect(
        DATABASE,
        timeout=30
    )

    db.execute(
        "PRAGMA busy_timeout=30000"
    )

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
        ORDER BY
            CAST(a.fecha_modificacion AS REAL) DESC
    """, (FECHA_MINIMA,))

    filas = c.fetchall()

    db.close()

    # Evitamos procesar copias idénticas.
    hashes = set()

    candidatos = []

    print()
    print("Analizando candidatos pendientes...")
    print()

    for (
        archivo_id,
        ruta,
        tipo,
        hash_archivo,
        fecha_modificacion,
    ) in filas:

        if hash_archivo:
            if hash_archivo in hashes:
                continue

            hashes.add(hash_archivo)

        puntaje, motivos = calcular_puntaje(ruta)

        duracion = obtener_duracion(ruta)

        if duracion is None:
            continue

        # Ignoramos clips prácticamente vacíos.
        if duracion < 20:
            continue

        candidatos.append({
            "id": archivo_id,
            "ruta": ruta,
            "tipo": tipo,
            "fecha": fecha_modificacion,
            "duracion": duracion,
            "puntaje": puntaje,
            "motivos": motivos,
        })

    # Primero relevancia.
    # Dentro del mismo puntaje, archivos cortos primero.
    candidatos.sort(
        key=lambda x: (
            -x["puntaje"],
            x["duracion"],
        )
    )

    print("=" * 78)
    print("ARCHIVISTA IA - RANKING DE CANDIDATOS PENDIENTES")
    print("=" * 78)

    print()
    print(
        "Candidatos únicos utilizables:",
        len(candidatos)
    )

    print()

    for posicion, candidato in enumerate(
        candidatos[:50],
        1
    ):

        try:
            fecha = datetime.fromtimestamp(
                candidato["fecha"]
            ).strftime("%Y-%m-%d")
        except Exception:
            fecha = "?"

        print("-" * 78)

        print(
            f"#{posicion:02d} | "
            f"ID {candidato['id']} | "
            f"{candidato['tipo']} | "
            f"PUNTOS {candidato['puntaje']} | "
            f"{formatear_duracion(candidato['duracion'])} | "
            f"{fecha}"
        )

        if candidato["motivos"]:
            print(
                "Motivos:",
                ", ".join(candidato["motivos"])
            )

        print(candidato["ruta"])

    print()
    print("=" * 78)


if __name__ == "__main__":
    main()