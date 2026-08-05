import logging

from core.config import LOG_DIR as log_dir

log_dir.mkdir(parents=True, exist_ok=True)

handlers = [
    logging.FileHandler(log_dir / "app.log", encoding="utf-8"),
]

# Set root logging handlers
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers = handlers

logger = logging.getLogger("aura")

info = logger.info
error = logger.error
warning = logger.warning
debug = logger.debug
critical = logger.critical
exception = logger.exception


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"aura.{name}")
