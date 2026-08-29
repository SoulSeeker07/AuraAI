"""
Forwarding shim for legacy imports of core.memory.memory.
Canonical implementation lives in src.core.memory.memory.
"""

from src.core.memory.memory import Memory

__all__ = ["Memory"]
