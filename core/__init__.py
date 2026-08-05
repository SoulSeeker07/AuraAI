"""
Core Aura Brain Components

Contains core system components including:
- Memory management
- Plugin system
- Tools
- Vision capabilities
- Workspace management
"""

import importlib.util
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_CORE = PROJECT_ROOT / "src" / "core"
if SRC_CORE.exists() and str(SRC_CORE) not in __path__:
    __path__.insert(0, str(SRC_CORE))

# Default logger
logger = logging.getLogger(__name__)


# Try to import logger using importlib (works regardless of path)
try:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    SRC_DIR = PROJECT_ROOT / "src"

    # Try to load logger from src/core/logger.py
    logger_path = SRC_DIR / "core" / "logger.py"
    if logger_path.exists():
        spec = importlib.util.spec_from_file_location("core.logger", logger_path)
        logger_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(logger_module)
        logger = logger_module.logger
    else:
        # Try to load logger from core/logger.py
        logger_path = Path(__file__).resolve().parent / "logger.py"
        if logger_path.exists():
            spec = importlib.util.spec_from_file_location("core.logger", logger_path)
            logger_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(logger_module)
            logger = logger_module.logger
        else:
            # Fallback to default logger
            logger = logging.getLogger(__name__)

    # Add project root to maintain core/ directory for other imports
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

except Exception as e:
    # Fallback to default logger if anything goes wrong
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not import logger from core.logger: {e}")

# Import core modules
# Import aura_core (the main Aura brain)
from . import aura_core, memory, plugins, tools, vision, workspace

__all__ = [
    "logger",
    "memory",
    "plugins",
    "tools",
    "vision",
    "workspace",
]
