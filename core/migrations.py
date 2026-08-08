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

    db.commit()