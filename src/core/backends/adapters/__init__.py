"""
Core Backend Adapters
Re-exports all backend adapters.
"""

from .antigravity_backend import AntigravityBackendAdapter
from .memory_backend import MemoryBackend, MemoryBackendAdapter
from .research_backend import ResearchEngineBackend

__all__ = [
    "AntigravityBackendAdapter",
    "MemoryBackend",
    "MemoryBackendAdapter",
    "ResearchEngineBackend",
]
