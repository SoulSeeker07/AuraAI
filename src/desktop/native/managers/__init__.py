# -*- coding: utf-8 -*-
"""
Native Windows Managers

Provides specialized managers for Windows desktop operations.
All managers inherit from BaseNativeManager and only contain Windows-specific code.
Cross-cutting concerns are handled by the execution pipeline.

Available Managers:
- WindowManager: Window operations (activate, close, resize, move, maximize, minimize)
- ClipboardManager: Clipboard operations (copy, paste, clear)
- DisplayManager: Display operations (detect, change mode, enumerate)
- AudioManager: Audio operations (volume, mute, devices)
- PowerManager: Power operations (sleep, shutdown, restart, lock)
- NetworkManager: Network operations (adapters, IP, DNS, Wi-Fi)
- ServiceManager: Service management
- RegistryManager: Registry operations
"""

from .base_manager import BaseNativeManager
from .window_manager import WindowManager
from .clipboard_manager import ClipboardManager
from .display_manager import DisplayManager
from .audio_manager import AudioManager
from .power_manager import PowerManager
from .network_manager import NetworkManager

__all__ = [
    "BaseNativeManager",
    "WindowManager",
    "ClipboardManager",
    "DisplayManager",
    "AudioManager",
    "PowerManager",
    "NetworkManager",
]

