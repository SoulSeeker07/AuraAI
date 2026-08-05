"""
Logger module for AuraAI

Provides logging functionality for AuraAI components.
All logs are written to a file; the CLI stays clean.
"""

import logging
import sys
from pathlib import Path

# Default location for the log file if the caller doesn't specify one
DEFAULT_LOG_FILE = Path(__file__).resolve().parent.parent / "Data" / "aura.log"


def setup_logger(
    name: str = "AuraAI",
    log_file: Path | None = None,
    level: int = logging.INFO,
    console_level: int | None = logging.WARNING,
) -> logging.Logger:
    """
    Set up and return a logger.

    Args:
        name: Logger name
        log_file: Path to log file. Defaults to Data/aura.log if not given.
        level: Logging level for the file handler (full detail)
        console_level: Logging level for the console handler.
                       Set to None to disable console output entirely
                       (fully silent CLI, everything still goes to file).

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler — always on, always UTF-8, so ✓/✗ and any other
    # non-ASCII characters never crash logging.
    resolved_log_file = Path(log_file) if log_file else DEFAULT_LOG_FILE
    resolved_log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(resolved_log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler — optional, and only for warnings/errors by default
    # so normal INFO chatter doesn't clutter the CLI prompt.
    if console_level is not None:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(formatter)
        console_handler.setEncoding("utf-8")
        logger.addHandler(console_handler)

    return logger


def get_logger(
    name: str = "AuraAI",
    log_file: Path | None = None,
    level: int = logging.INFO,
    console_level: int | None = logging.WARNING,
) -> logging.Logger:
    """
    Convenience alias for setup_logger, matching the common
    `get_logger(__name__)` pattern used elsewhere in the codebase.
    """
    return setup_logger(name, log_file, level, console_level)


# Default logger: everything goes to Data/aura.log,
# console only shows WARNING and above (clean CLI).
logger = setup_logger("")

info = logger.info
error = logger.error
warning = logger.warning
debug = logger.debug
critical = logger.critical
exception = logger.exception

