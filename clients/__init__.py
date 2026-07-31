"""
Clients package for AuraAI

Provides different client implementations:
- CLI Client: Command-line interface
- GUI Client: Graphical user interface
- Voice Client: Voice interface
- API Client: REST API interface
"""

from .cli_client import CLIClient
from .gui_client import GUIClient

__all__ = ['CLIClient', 'GUIClient']
