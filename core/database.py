import sqlite3
from datetime import datetime

from config.settings import DATABASE


class Database:

    def __init__(self):

        DATABASE.parent.mkdir(exist_ok=True)

        self.conn = sqlite3.connect(DATABASE)
        print("Base:", DATABASE.resolve())

        from core.migrations import migrate
        migrate(self.conn)

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

            hash TEXT,

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
                hash,
                fecha_registro
            )
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                archivo["ruta"],
                archivo["nombre"],
                archivo["extension"],
                archivo["tamano"],
                archivo["fecha_modificacion"],
                archivo["tipo"],
                None,
                datetime.now().isoformat()
            ))

            self.conn.commit()

        except Exception:
            import traceback
            traceback.print_exc()

    def close(self):

        self.conn.close()

    def actualizar_hash(self, ruta, hash_archivo):

        cursor = self.conn.cursor()

        cursor.execute("""
            UPDATE archivos
            SET hash_archivo = ?
            WHERE ruta = ?
        """, (hash_archivo, ruta))

        self.conn.commit()