import sqlite3
from difflib import SequenceMatcher

from config.settings import DATABASE


def buscar_texto(texto):
    db = sqlite3.connect(DATABASE)
    c = db.cursor()

    patron = f"%{texto}%"

    c.execute("""
        SELECT
            t.archivo_id,
            a.ruta,
            t.inicio,
            t.fin,
            t.texto
        FROM transcripciones t
        JOIN archivos a
            ON a.id = t.archivo_id
        WHERE t.texto LIKE ?
        ORDER BY a.ruta, t.inicio
    """, (patron,))

    resultados = c.fetchall()

    db.close()

    return resultados


def buscar_aproximado(texto_buscado, similitud_minima=0.75):
    db = sqlite3.connect(DATABASE)
    c = db.cursor()

    c.execute("""
        SELECT
            t.archivo_id,
            a.ruta,
            t.inicio,
            t.fin,
            t.texto
        FROM transcripciones t
        JOIN archivos a
            ON a.id = t.archivo_id
        ORDER BY a.ruta, t.inicio
    """)

    coincidencias = []

    buscado = texto_buscado.lower()

    for fila in c.fetchall():
        texto = fila[4].lower()
        palabras = texto.split()

        cantidad = len(buscado.split())

        for i in range(len(palabras)):
            fragmento = " ".join(
                palabras[i:i + cantidad]
            )

            similitud = SequenceMatcher(
                None,
                buscado,
                fragmento
            ).ratio()

            if similitud >= similitud_minima:
                coincidencias.append(
                    (
                        similitud,
                        fila[0],
                        fila[1],
                        fila[2],
                        fila[3],
                        fila[4]
                    )
                )

                break

    db.close()

    coincidencias.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return coincidencias