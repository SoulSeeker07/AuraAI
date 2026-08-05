"""
Core Backend Adapters
Re-exports all backend adapters.
"""

from .antigravity_backend import AntigravityBackend
from .desktop_backend import DesktopEngineBackend
from .gemini_backend import GeminiBackend
from .groq_backend import GroqBackend

__all__ = [
    "DesktopEngineBackend",
    "GroqBackend",
    "GeminiBackend",
    "AntigravityBackend",
]
