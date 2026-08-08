import sqlite3

from config.settings import DATABASE


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


if __name__ == "__main__":
    pendientes = obtener_pendientes()

    print("Archivos multimedia pendientes:", len(pendientes))

    for fila in pendientes[:10]:
        print(fila)