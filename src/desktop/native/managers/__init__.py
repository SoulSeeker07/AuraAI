"""
Native Windows Managers

Provides specialized managers for Windows desktop operations.
All managers inherit from BaseNativeManager and only contain Windows-specific code.
Cross-cutting concerns are handled by the execution pipeline.

Available Managers:
- WindowManager: Window operations (activate, close, resize, move, maximize, minimize)
- AdvancedWindowManager: Spatial snapping, transparency, always-on-top, tiling
- ClipboardManager: Clipboard operations (copy, paste, clear)
- DisplayManager: Display operations (detect, change mode, enumerate)
- AudioManager: Audio operations (volume, mute, devices)
- PowerManager: Power operations (sleep, shutdown, restart, lock)
- NetworkManager: Network operations (adapters, IP, DNS, Wi-Fi)
- ServiceManager: Service management
- RegistryManager: Registry operations
- FileManager: File system CRUD and extended manipulation
- InputManager: Keyboard & mouse simulation engine
- TerminalManager: PowerShell / shell command execution & session manager
- NotificationManager: Windows notifications, alerts, and sounds
- SchedulerManager: Task scheduler, timers, and interval loops
- ScreenActionManager: Screenshot-to-action computer-use closed loop
- SettingsManager: Windows personalization, dark mode, wallpaper, startup
- SoftwareManager: Winget, pip, npm package installations
- SecurityManager: Windows Firewall, Defender antivirus, temp cleanup
"""

from .advanced_window_manager import AdvancedWindowManager
from .audio_manager import AudioManager
from .base_manager import BaseNativeManager
from .clipboard_manager import ClipboardManager
from .display_manager import DisplayManager
from .file_manager import FileManager
from .input_manager import InputManager
from .native_manager_registry import NativeManagerRegistry
from .network_manager import NetworkManager
from .notification_manager import NotificationManager
from .power_manager import PowerManager
from .scheduler_manager import SchedulerManager
from .screen_action_manager import ScreenActionManager
from .security_manager import SecurityManager
from .settings_manager import SettingsManager
from .software_manager import SoftwareManager
from .terminal_manager import TerminalManager
from .uia_manager import UIAManager
from .window_manager import WindowManager

__all__ = [
    "BaseNativeManager",
    "NativeManagerRegistry",
    "WindowManager",
    "AdvancedWindowManager",
    "ClipboardManager",
    "DisplayManager",
    "AudioManager",
    "PowerManager",
    "NetworkManager",
    "UIAManager",
    "FileManager",
    "InputManager",
    "TerminalManager",
    "NotificationManager",
    "SchedulerManager",
    "ScreenActionManager",
    "SettingsManager",
    "SoftwareManager",
    "SecurityManager",
]
