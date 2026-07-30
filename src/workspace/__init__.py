"""
Workspace Awareness Module

Provides desktop context awareness for Aura.

Features:
- Active window monitoring
- Project auto-detection
- Git repository awareness
- Clipboard monitoring
- Running applications tracking
- Terminal context
"""

from .workspace_manager import WorkspaceManager
from .models import (
    WorkspaceState,
    ActiveWindow,
    CurrentProject,
    GitRepository,
    OpenFile,
    TerminalContext,
    ClipboardContext,
    RunningApplication,
    BrowserContext,
    PlatformType,
    ProjectType,
    TerminalType
)

__all__ = [
    'WorkspaceManager',
    'WorkspaceState',
    'ActiveWindow',
    'CurrentProject',
    'GitRepository',
    'OpenFile',
    'TerminalContext',
    'ClipboardContext',
    'RunningApplication',
    'BrowserContext',
    'PlatformType',
    'ProjectType',
    'TerminalType',
]

__version__ = '1.0.0'
