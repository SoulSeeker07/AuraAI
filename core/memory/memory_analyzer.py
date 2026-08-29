"""
Re-export shim for core.memory.memory_analyzer -> src.core.memory.memory_analyzer.
Canonical implementation lives in src/core/memory/memory_analyzer.py.
"""

from src.core.memory.memory_analyzer import MemoryAnalyzer

__all__ = ["MemoryAnalyzer"]
