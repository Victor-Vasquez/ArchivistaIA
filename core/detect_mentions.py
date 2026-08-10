import re
import time
import unicodedata
from difflib import SequenceMatcher

from faster_whisper import WhisperModel


MODELO = "medium"

UMBRAL_NOMBRE = 0.80
UMBRAL_APELLIDO = 0.80

NOMBRES_CELSO = [
    "celso",
    "selso",
    "celzo",
]

APELLIDOS_ORTIZ = [
    "ortiz",
    "ortis",
    "ortís",
]


def normalizar(texto):
    texto = texto.lower()

    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )

    texto = re.sub(
        r"[^a-z0-9ñ ]",
        " ",
        texto
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


def similitud(palabra, candidatos):
    mejor = 0.0

    for candidato in candidatos:
        valor = SequenceMatcher(
            None,
            palabra,
            normalizar(candidato)
        ).ratio()

        if valor > mejor:
            mejor = valor

    return mejor


def detectar_nombre_completo(texto):
    texto_normalizado = normalizar(texto)
    palabras = texto_normalizado.split()

    for i, palabra in enumerate(palabras):
        similitud_nombre = similitud(
            palabra,
            NOMBRES_CELSO
        )

        if similitud_nombre < UMBRAL_NOMBRE:
            continue

        # Buscamos Ortiz en las siguientes 4 palabras
        limite = min(
            len(palabras),
            i + 5
        )

        for j in range(i + 1, limite):
            similitud_apellido = similitud(
                palabras[j],
                APELLIDOS_ORTIZ
            )

            if similitud_apellido >= UMBRAL_APELLIDO:
                return {
                    "nombre": palabra,
                    "apellido": palabras[j],
                    "similitud_nombre": similitud_nombre,
                    "similitud_apellido": similitud_apellido,
                }

    return None


def detectar_menciones(ruta):
    print(f"Cargando Whisper {MODELO}...")

    modelo = WhisperModel(
        MODELO,
        device="cpu",
        compute_type="int8"
    )

    print()
    print("Analizando:")
    print(ruta)
    print()

    inicio = time.time()

    segmentos, info = modelo.transcribe(
        ruta,
        language="es",
        beam_size=1,
        vad_filter=True
    )

    coincidencias = []
    segmentos_revisados = 0

    for segmento in segmentos:
        segmentos_revisados += 1

        texto = segmento.text.strip()

        if not texto:
            continue

        resultado = detectar_nombre_completo(
            texto
        )

        if resultado:
            coincidencia = {
                "inicio": segmento.start,
                "fin": segmento.end,
                "texto": texto,
                **resultado
            }

            coincidencias.append(
                coincidencia
            )

            print(
                f"[{segmento.start:.1f} - "
                f"{segmento.end:.1f}] "
                f"{texto}"
            )

            print(
                "   Detectado:",
                resultado["nombre"],
                resultado["apellido"],
                "| similitud:",
                f'{resultado["similitud_nombre"]:.2f}',
                f'{resultado["similitud_apellido"]:.2f}'
            )

    tiempo = time.time() - inicio

    print()
    print("=" * 60)
    print("ANALISIS TERMINADO")
    print(
        f"Segmentos revisados: "
        f"{segmentos_revisados}"
    )
    print(
        f"Coincidencias: "
        f"{len(coincidencias)}"
    )
    print(
        f"Tiempo: "
        f"{tiempo:.2f} segundos"
    )
    print("=" * 60)

    return coincidencias


if __name__ == "__main__":
    detectar_menciones(
        r"C:\vvasquez\hnoJoel\ArchivistaIA\temp\prueba_whisper.wav"
    )