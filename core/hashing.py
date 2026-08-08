from pathlib import Path
import hashlib


def sha256_file(ruta):

    ruta = Path(ruta)

    sha = hashlib.sha256()

    with ruta.open("rb") as f:

        while True:

            bloque = f.read(1024 * 1024)

            if not bloque:
                break

            sha.update(bloque)

    return sha.hexdigest()