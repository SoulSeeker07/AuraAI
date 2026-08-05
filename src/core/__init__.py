from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ROOT_CORE = PROJECT_ROOT / "core"
if ROOT_CORE.exists() and str(ROOT_CORE) not in __path__:
    __path__.append(str(ROOT_CORE))

from . import planning  # noqa: E402

__all__ = [
    "planning",
]
