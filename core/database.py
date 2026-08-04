import sqlite3
from datetime import datetime

from config.settings import DATABASE


class Database:

    def __init__(self):

        DATABASE.parent.mkdir(exist_ok=True)

        self.conn = sqlite3.connect(DATABASE)
        print("Base:", DATABASE.resolve())

        self.create_tables()


    def create_tables(self):

        cursor = self.conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS archivos(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            ruta TEXT UNIQUE,

            nombre TEXT,

            extension TEXT,

            tamano INTEGER,

            fecha_modificacion TEXT,

            tipo TEXT,

            estado TEXT DEFAULT 'PENDIENTE',

            fecha_registro TEXT

        )
        """)

        self.conn.commit()


    def insert_file(self, archivo):

        cursor = self.conn.cursor()

        try:
            cursor.execute("""
            INSERT INTO archivos
            (
                ruta,
                nombre,
                extension,
                tamano,
                fecha_modificacion,
                tipo,
                fecha_registro
            )
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                archivo["ruta"],
                archivo["nombre"],
                archivo["extension"],
                archivo["tamano"],
                archivo["fecha_modificacion"],
                archivo["tipo"],
                datetime.now().isoformat()
            ))

            print("Rowcount:", cursor.rowcount)
            print("LastRowId:", cursor.lastrowid)

            self.conn.commit()

            cursor.execute("SELECT COUNT(*) FROM archivos")
            print("Total registros:", cursor.fetchone()[0])

        except Exception as e:
            import traceback
            traceback.print_exc()

    def close(self):

        self.conn.close()