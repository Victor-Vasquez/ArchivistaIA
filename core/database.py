import sqlite3

from config.settings import DATABASE

DATABASE.parent.mkdir(exist_ok=True)


class Database:

    def __init__(self):

        self.conn = sqlite3.connect(DATABASE)

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

            estado TEXT DEFAULT 'PENDIENTE'

        )
        """)

        self.conn.commit()

    def close(self):

        self.conn.close()