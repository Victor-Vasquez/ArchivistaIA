import time
from faster_whisper import WhisperModel


RUTA = r"E:\z\__NO_INCLUIR__\Puppy el niño de los anillos.mp4"

print("Cargando modelo...")

model = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8"
)

print("Transcribiendo...")
inicio = time.time()
segments, info = model.transcribe(
    RUTA,
    language="es",
    beam_size=1
)

print("Idioma:", info.language)

for segment in segments:
    print(
        f"[{segment.start:.1f} - {segment.end:.1f}] "
        f"{segment.text}"
    )
fin = time.time()
print(f"\nTiempo total: {fin - inicio:.2f} segundos")