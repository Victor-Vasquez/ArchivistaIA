from pathlib import Path

APP_NAME = "Archivista IA"
VERSION = "0.2.0"

# Unidad a analizar
ROOT_FOLDER = Path(r"E:\\")

# Base de datos
DATABASE = Path("data") / "archivista.db"

# Carpetas internas
LOG_FOLDER = Path("logs")
CACHE_FOLDER = Path("cache")
TEMP_FOLDER = Path("temp")


# Extensiones multimedia

VIDEO_EXTENSIONS = {
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".mpeg",
    ".mpg",
    ".wmv",
    ".m2ts",
    ".mts",
    ".vob",
}

AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".flac",
    ".ogg",
    ".aac",
    ".m4a",
    ".wma",
}


# Carpetas que no necesitan análisis pesado

IGNORE_FOLDERS = {
    "$RECYCLE.BIN",
    "System Volume Information",
    "WindowsImageBackup",
    "instaladores",
    "nuevos_instaladores",
    "Mac Driver",
}