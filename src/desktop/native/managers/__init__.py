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

from .audio_manager import AudioManager
from .base_manager import BaseNativeManager
from .clipboard_manager import ClipboardManager
from .display_manager import DisplayManager
from .native_manager_registry import NativeManagerRegistry
from .network_manager import NetworkManager
from .power_manager import PowerManager
from .uia_manager import UIAManager
from .window_manager import WindowManager

__all__ = [
    "BaseNativeManager",
    "NativeManagerRegistry",
    "WindowManager",
    "ClipboardManager",
    "DisplayManager",
    "AudioManager",
    "PowerManager",
    "NetworkManager",
    "UIAManager",
]
