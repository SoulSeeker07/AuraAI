"""
Core Aura Brain Components

Contains core system components including:
- Local responder
- Configuration
- Event bus
- Hotkeys
- Live screen
- Overlay manager
- Plugin manager
- Router
- Screen context
- Settings
- Window manager
- Knowledge (RAG 2.0)
"""

from . import local_responder
from . import config
from . import event_bus
from . import hotkeys
from . import live_screen
from . import overlay_manager
from . import plugin_manager
from . import router
from . import screen_context
from . import settings
from . import window_manager

__all__ = [
    'local_responder',
    'config',
    'event_bus',
    'hotkeys',
    'live_screen',
    'overlay_manager',
    'plugin_manager',
    'router',
    'screen_context',
    'settings',
    'window_manager',
]