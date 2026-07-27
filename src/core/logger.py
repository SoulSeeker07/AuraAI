import logging

from core.config import LOG_DIR

LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "app.log"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("aura")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"aura.{name}")
