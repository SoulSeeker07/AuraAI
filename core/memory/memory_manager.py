"""
Re-export shim for core.memory.memory_manager -> src.core.memory.memory_manager.
Canonical implementation lives in src/core/memory/memory_manager.py.
"""

from src.core.memory.memory_manager import MemoryManager

__all__ = ["MemoryManager"]
