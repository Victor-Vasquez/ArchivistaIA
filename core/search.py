import sqlite3

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