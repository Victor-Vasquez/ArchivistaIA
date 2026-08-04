import logging

from config.settings import LOG_FOLDER

LOG_FOLDER.mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOG_FOLDER / "archivista.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("Archivista")