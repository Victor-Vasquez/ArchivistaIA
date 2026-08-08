from faster_whisper import WhisperModel


print("Cargando modelo Whisper...")

model = WhisperModel(
    "tiny",
    device="cpu",
    compute_type="int8"
)

print("Modelo cargado correctamente.")