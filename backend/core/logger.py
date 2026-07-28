from loguru import logger
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure loguru: rotate at 5 MB and keep 5 files
logger.remove()
logger.add(LOG_DIR / "aura.log", rotation="5 MB", retention=5, level="DEBUG", encoding="utf-8")

# Expose a stable name used by the codebase
log = logger
