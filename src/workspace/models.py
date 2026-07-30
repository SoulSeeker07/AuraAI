"""
Workspace State Models

Core data structures for desktop context awareness.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class PlatformType(str, Enum):
    """Platform type enumeration"""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"


class TerminalType(str, Enum):
    """Terminal type enumeration"""
    POWERSHELL = "powershell"
    CMD = "cmd"
    WSL = "wsl"
    GIT_BASH = "gitbash"
    UNKNOWN = "unknown"


class ProjectType(str, Enum):
    """Project type enumeration"""
    PYTHON = "python"
    NODE = "node"
    DOTNET = "dotnet"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    WEB = "web"
    UNKNOWN = "unknown"


@dataclass
class OpenFile:
    """Represents an open file"""
    path: str
    name: str
    modified: bool = False
    line_number: Optional[int] = None
    cursor_position: Optional[int] = None
    last_accessed: datetime = field(default_factory=datetime.now)

    def __hash__(self):
        return hash(self.path)


@dataclass
class GitRepository:
    """Represents a git repository"""
    path: str
    branch: str
    remote_url: Optional[str] = None
    commit_hash: Optional[str] = None
    modified_files: List[str] = field(default_factory=list)
    uncommitted_changes: int = 0
    is_dirty: bool = False

    @property
    def repo_name(self) -> str:
        """Get repository name from path"""
        return str(Path(self.path).name)


@dataclass
class CurrentProject:
    """Represents the current active project"""
    path: str
    name: str
    type: ProjectType = ProjectType.UNKNOWN
    git_repo: Optional[GitRepository] = None
    workspace_folder: Optional[str] = None
    detected_at: datetime = field(default_factory=datetime.now)

    @property
    def has_git(self) -> bool:
        """Check if project has git repository"""
        return self.git_repo is not None

    @property
    def is_dirty(self) -> bool:
        """Check if project has uncommitted changes"""
        return self.git_repo is not None and self.git_repo.is_dirty


@dataclass
class ActiveWindow:
    """Represents the currently active window"""
    title: str
    app_name: str
    process_name: str
    window_id: Optional[int] = None
    rect: Optional[Dict[str, int]] = None  # x, y, width, height
    is_minimized: bool = False
    is_maximized: bool = False

    @property
    def is_in_workspace(self) -> bool:
        """Check if window is within workspace bounds"""
        if self.rect is None:
            return True
        return (
            self.rect.get('x', 0) >= 0 and
            self.rect.get('y', 0) >= 0 and
            self.rect.get('width', 100) > 0 and
            self.rect.get('height', 100) > 0
        )


@dataclass
class RunningApplication:
    """Represents a running application"""
    name: str
    process_name: str
    window_title: str = ""
    is_foreground: bool = False
    pid: Optional[int] = None

    @property
    def is_editor(self) -> bool:
        """Check if app is a code editor"""
        editor_apps = {'vscode', 'cursor', 'code', 'sublime', 'atom', 'idea'}
        return self.process_name.lower() in editor_apps

    @property
    def is_browser(self) -> bool:
        """Check if app is a browser"""
        browser_apps = {'chrome', 'edge', 'firefox', 'safari', 'brave'}
        return self.process_name.lower() in browser_apps


@dataclass
class TerminalContext:
    """Represents terminal state"""
    type: TerminalType
    working_directory: str
    running_commands: List[str] = field(default_factory=list)
    current_command: Optional[str] = None
    last_command_output: Optional[str] = None

    @property
    def is_wsl(self) -> bool:
        """Check if running in WSL"""
        return self.type == TerminalType.WSL


@dataclass
class ClipboardContext:
    """Represents clipboard state"""
    text: Optional[str] = None
    code: Optional[str] = None
    image: Optional[str] = None  # Path to image if copied
    is_text: bool = False
    is_code: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def has_content(self) -> bool:
        """Check if clipboard has content"""
        return self.text is not None and len(self.text.strip()) > 0


@dataclass
class BrowserContext:
    """Represents browser state"""
    current_url: Optional[str] = None
    current_title: Optional[str] = None
    selected_text: Optional[str] = None
    active_tab: int = 0
    total_tabs: int = 1
    downloads: List[str] = field(default_factory=list)


@dataclass
class WorkspaceState:
    """
    Single source of truth for desktop context.

    Contains all information about the user's current desktop state.
    """
    # Core desktop info
    platform: PlatformType = PlatformType.WINDOWS
    active_window: Optional[ActiveWindow] = None

    # Project info
    current_project: Optional[CurrentProject] = None
    workspace_folder: Optional[str] = None

    # File context
    open_files: List[OpenFile] = field(default_factory=list)
    recent_files: List[str] = field(default_factory=list)
    pinned_files: List[str] = field(default_factory=list)
    modified_files: List[str] = field(default_factory=list)

    # Git awareness
    git_repo: Optional[GitRepository] = None

    # Terminal
    terminal: Optional[TerminalContext] = None

    # Clipboard
    clipboard: Optional[ClipboardContext] = None

    # Running applications
    running_apps: List[RunningApplication] = field(default_factory=list)

    # Browser (optional)
    browser: Optional[BrowserContext] = None

    # Metadata
    last_updated: datetime = field(default_factory=datetime.now)
    workspace_folder_path: Optional[str] = None

    def __post_init__(self):
        """Post-initialization setup"""
        if self.active_window:
            self.last_updated = datetime.now()

    @property
    def has_active_window(self) -> bool:
        """Check if there's an active window"""
        return self.active_window is not None

    @property
    def has_active_project(self) -> bool:
        """Check if there's an active project"""
        return self.current_project is not None

    @property
    def has_git_repo(self) -> bool:
        """Check if there's a git repository"""
        return self.git_repo is not None

    @property
    def is_dirty(self) -> bool:
        """Check if project has uncommitted changes"""
        return self.current_project is not None and self.current_project.is_dirty

    @property
    def open_editor_files(self) -> List[OpenFile]:
        """Get open files from editors"""
        return [f for f in self.open_files if f.path.endswith(('.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cs', '.go', '.rs', '.md'))]

    @property
    def code_files_modified(self) -> int:
        """Count modified code files"""
        return len(self.modified_files)

    @property
    def running_app_count(self) -> int:
        """Count running applications"""
        return len(self.running_apps)

    def update_timestamp(self):
        """Update the last_updated timestamp"""
        self.last_updated = datetime.now()
        if self.active_window:
            self.active_window.last_accessed = self.last_updated


# Utility functions for workspace state

def get_context_summary(state: WorkspaceState) -> str:
    """
    Generate a human-readable summary of workspace state.

    Args:
        state: WorkspaceState object

    Returns:
        String summary of current context
    """
    summary_parts = []

    # Active window
    if state.active_window:
        summary_parts.append(f"Window: {state.active_window.title} ({state.active_window.app_name})")

    # Current project
    if state.current_project:
        summary_parts.append(f"Project: {state.current_project.name}")
        if state.current_project.git_repo:
            summary_parts.append(f"  - Branch: {state.current_project.git_repo.branch}")
            if state.current_project.git_repo.is_dirty:
                summary_parts.append(f"  - Modified files: {state.current_project.git_repo.modified_files}")

    # Open files
    if state.open_files:
        open_count = len(state.open_files)
        summary_parts.append(f"Open files: {open_count}")

    # Running apps
    if state.running_apps:
        editor_apps = [app for app in state.running_apps if app.is_editor]
        if editor_apps:
            summary_parts.append(f"Active editor: {', '.join(set(app.name for app in editor_apps))}")

    return " | ".join(summary_parts)
