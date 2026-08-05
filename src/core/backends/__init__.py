"""
Core Backends Package
Execution backend adapters and registry.
"""

from .adapters import (
    AntigravityBackend,
    DesktopEngineBackend,
    GeminiBackend,
    GroqBackend,
)
from .backend_registry import BackendRegistry
from .base_backend import BaseBackendAdapter

__all__ = [
    "BaseBackendAdapter",
    "BackendRegistry",
    "DesktopEngineBackend",
    "GroqBackend",
    "GeminiBackend",
    "AntigravityBackend",
]
