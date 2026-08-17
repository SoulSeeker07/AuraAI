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

from .models import (
    ActiveWindow,
    BrowserContext,
    ClipboardContext,
    CurrentProject,
    GitRepository,
    OpenFile,
    PlatformType,
    ProjectType,
    RunningApplication,
    TerminalContext,
    TerminalType,
    WorkspaceState,
)
from .editor_tracker import EditorTracker
from .workspace_manager import WorkspaceManager

__all__ = [
    "WorkspaceManager",
    "WorkspaceState",
    "ActiveWindow",
    "CurrentProject",
    "GitRepository",
    "OpenFile",
    "TerminalContext",
    "ClipboardContext",
    "RunningApplication",
    "BrowserContext",
    "PlatformType",
    "ProjectType",
    "TerminalType",
    "EditorTracker",
]

__version__ = "1.0.0"
