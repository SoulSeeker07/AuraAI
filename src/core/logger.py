import logging
from datetime import datetime

from core.config import LOG_DIR as log_dir

# ── Session-scoped log directory ─────────────────────────────────────────────
# Structure:  logs/YYYY-MM-DD/session_HHMMSS.log
# Each `python main.py` launch creates a fresh file.
# The session path is printed to the log on startup — grep or open directly.

_session_start = datetime.now()
_day_dir = log_dir / _session_start.strftime("%Y-%m-%d")
_day_dir.mkdir(parents=True, exist_ok=True)

_session_log = _day_dir / _session_start.strftime("session_%H%M%S.log")

# ── Formatter ─────────────────────────────────────────────────────────────────
_fmt = logging.Formatter(
    fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# ── Handlers ──────────────────────────────────────────────────────────────────
_session_handler = logging.FileHandler(_session_log, encoding="utf-8")
_session_handler.setFormatter(_fmt)

# ── Root logger ───────────────────────────────────────────────────────────────
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)   # TEMP: DEBUG for VAD diagnostics — revert to INFO after test
root_logger.handlers = [_session_handler]

logger = logging.getLogger("aura")

# Print session log path at startup so it's easy to find
logger.info(f"Session log: {_session_log}")

# Convenience aliases used by other modules via `from core import logger`
info      = logger.info
error     = logger.error
warning   = logger.warning
debug     = logger.debug
critical  = logger.critical
exception = logger.exception


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"aura.{name}")
