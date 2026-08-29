"""
Re-export shim for core.aura_core -> src.core.aura_core.
Canonical implementation lives in src/core/aura_core.py.
"""

from src.core.aura_core import AuraCore, AuraCoreStatus

__all__ = ["AuraCore", "AuraCoreStatus"]
