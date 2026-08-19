"""
Autonomy Telemetry Watchers (M24 Phase 5 & 6)
Location: src/autonomy/watchers/__init__.py

Exposes dumb telemetry producers (FilesystemWatcher, ProcessMonitor).
"""

from .filesystem import FilesystemWatcher
from .process import ProcessMonitor

__all__ = [
    "FilesystemWatcher",
    "ProcessMonitor",
]
