import hashlib


def calcular_hash(ruta, bloque=1024 * 1024):
    sha256 = hashlib.sha256()

    with open(ruta, "rb") as archivo:
        while True:
            datos = archivo.read(bloque)

            if not datos:
                break

            sha256.update(datos)

    return sha256.hexdigest()