import sqlite3

from config.settings import DATABASE


def guardar_segmento(archivo_id, inicio, fin, texto):
    db = sqlite3.connect(DATABASE)
    c = db.cursor()

    c.execute("""
        INSERT INTO transcripciones (
            archivo_id,
            inicio,
            fin,
            texto
        )
        VALUES (?, ?, ?, ?)
    """, (
        archivo_id,
        inicio,
        fin,
        texto
    ))

    db.commit()
    db.close()