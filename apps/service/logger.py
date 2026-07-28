from loguru import logger
from pathlib import Path
import sys

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Clear default handlers and add our structured handler
logger.remove()
logger.add(sys.stderr, level="DEBUG")
logger.add(LOG_DIR / "service.log", rotation="5 MB", retention=5, level="DEBUG", encoding="utf-8")

def get_logger(name: str = "aura.service"):
    return logger.bind(component=name)
