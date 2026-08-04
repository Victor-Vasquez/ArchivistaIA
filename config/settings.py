from pathlib import Path

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

APP_NAME = "Archivista IA"
VERSION = "0.1.0"

# Disco que se analizará
ROOT_FOLDER = Path(r"E:\\")

# Base de datos
DATABASE = Path("data") / "archivista.db"

# Directorios
LOG_FOLDER = Path("logs")
CACHE_FOLDER = Path("cache")
TEMP_FOLDER = Path("temp")

# Extensiones soportadas

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