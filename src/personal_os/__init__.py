"""
Personal OS Subsystem
Location: src/personal_os/__init__.py

Manages digital environment state, daily context synthesis,
workspace indexed search, and persistent trigger-based automation.
"""

from __future__ import annotations

from .state_store import PersonalOSStateStore, PersonalOSTrigger

__all__ = ["PersonalOSStateStore", "PersonalOSTrigger"]
