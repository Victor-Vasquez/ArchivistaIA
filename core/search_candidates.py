import sqlite3

from config.settings import DATABASE


def obtener_candidatos():
    db = sqlite3.connect(DATABASE)
    c = db.cursor()

    c.execute("""
        SELECT
            id,
            ruta,
            tipo
        FROM archivos
        WHERE tipo IN ('AUDIO', 'VIDEO')
          AND LOWER(ruta) LIKE '%iglesia%'
        ORDER BY id
    """)

    resultados = c.fetchall()

    db.close()

    return resultados


if __name__ == "__main__":
    candidatos = obtener_candidatos()

    print("Candidatos:", len(candidatos))

    for fila in candidatos[:20]:
        print(fila)