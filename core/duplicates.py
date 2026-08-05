from core.database import Database


def posibles_duplicados():
    db = Database()
    c = db.conn.cursor()

    c.execute("""
        SELECT
            tamano,
            COUNT(*) AS cantidad
        FROM archivos
        GROUP BY tamano
        HAVING COUNT(*) > 1
        ORDER BY cantidad DESC
    """)

    resultado = c.fetchall()

    db.close()

    return resultado
