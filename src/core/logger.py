import logging

from core.config import log_dir

log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "app.log"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger("aura")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"aura.{name}")
