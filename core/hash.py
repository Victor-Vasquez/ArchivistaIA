import hashlib

def calcular_hash(ruta):
    return hashlib.sha256(open(ruta, "rb").read()).hexdigest()