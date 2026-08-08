def migrate(db):

    print("Ejecutando migraciones...")

    columnas = [
        "fecha_modificacion TEXT",
        "hash_archivo TEXT",
        "tipo_documento TEXT"
    ]

    for columna in columnas:
        try:
            db.execute(f"ALTER TABLE archivos ADD COLUMN {columna}")
            print(f"Agregada columna: {columna}")
        except Exception:
            pass
        
    db.execute("""
    CREATE TABLE IF NOT EXISTS transcripciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        archivo_id INTEGER NOT NULL,
        inicio REAL NOT NULL,
        fin REAL NOT NULL,
        texto TEXT NOT NULL,
        FOREIGN KEY (archivo_id) REFERENCES archivos(id)
    )
    """)


    db.commit()