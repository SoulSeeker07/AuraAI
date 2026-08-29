"""
Re-export shim for core.memory.memory_manager_v2 -> src.core.memory.memory_manager_v2.
Canonical implementation lives in src/core/memory/memory_manager_v2.py.
"""

from src.core.memory.memory_manager_v2 import MemoryManagerV2

__all__ = ["MemoryManagerV2"]
