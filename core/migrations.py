def migrate(db):

    columnas = [
        "fecha_modificacion TEXT",
        "hash_archivo TEXT",
        "tipo_documento TEXT"
    ]

    for columna in columnas:
        try:
            db.execute(
                f"ALTER TABLE archivos ADD COLUMN {columna}"
            )
        except:
            pass