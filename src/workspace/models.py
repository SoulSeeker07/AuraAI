"""
Workspace State Models

Core data structures for desktop context awareness.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


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
    line_number: int | None = None
    cursor_position: int | None = None
    last_accessed: datetime = field(default_factory=datetime.now)

    def __hash__(self):
        return hash(self.path)


@dataclass
class GitRepository:
    """Represents a git repository"""

    path: str
    branch: str = "main"
    remote_url: str | None = None
    commit_hash: str | None = None
    modified_files: list[str] = field(default_factory=list)
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
    git_repo: GitRepository | None = None
    workspace_folder: str | None = None
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
    window_id: int | None = None
    rect: dict[str, int] | None = None  # x, y, width, height
    is_minimized: bool = False
    is_maximized: bool = False

    @property
    def is_in_workspace(self) -> bool:
        """Check if window is within workspace bounds"""
        if self.rect is None:
            return True
        return (
            self.rect.get("x", 0) >= 0
            and self.rect.get("y", 0) >= 0
            and self.rect.get("width", 100) > 0
            and self.rect.get("height", 100) > 0
        )


@dataclass
class RunningApplication:
    """Represents a running application"""

    name: str
    process_name: str
    window_title: str = ""
    is_foreground: bool = False
    pid: int | None = None

    @property
    def is_editor(self) -> bool:
        """Check if app is a code editor"""
        editor_apps = {"vscode", "cursor", "code", "sublime", "atom", "idea"}
        return self.process_name.lower() in editor_apps

    @property
    def is_browser(self) -> bool:
        """Check if app is a browser"""
        browser_apps = {"chrome", "edge", "firefox", "safari", "brave"}
        return self.process_name.lower() in browser_apps


@dataclass
class TerminalContext:
    """Represents terminal state"""

    type: TerminalType
    working_directory: str
    running_commands: list[str] = field(default_factory=list)
    current_command: str | None = None
    last_command_output: str | None = None

    @property
    def is_wsl(self) -> bool:
        """Check if running in WSL"""
        return self.type == TerminalType.WSL


@dataclass
class ClipboardContext:
    """Represents clipboard state"""

    text: str | None = None
    code: str | None = None
    image: str | None = None  # Path to image if copied
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

    current_url: str | None = None
    current_title: str | None = None
    selected_text: str | None = None
    active_tab: int = 0
    total_tabs: int = 1
    downloads: list[str] = field(default_factory=list)


@dataclass
class WorkspaceState:
    """
    Single source of truth for desktop context.

    Contains all information about the user's current desktop state.
    """

    # Core desktop info
    platform: PlatformType = PlatformType.WINDOWS
    active_window: ActiveWindow | None = None

    # Project info
    current_project: CurrentProject | None = None
    workspace_folder: str | None = None

    # File context
    open_files: list[OpenFile] = field(default_factory=list)
    recent_files: list[str] = field(default_factory=list)
    pinned_files: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)

    # Git awareness
    git_repo: GitRepository | None = None

    # Terminal
    terminal: TerminalContext | None = None

    # Clipboard
    clipboard: ClipboardContext | None = None

    # Running applications
    running_apps: list[RunningApplication] = field(default_factory=list)

    # Browser (optional)
    browser: BrowserContext | None = None

    # Metadata
    last_updated: datetime = field(default_factory=datetime.now)
    workspace_folder_path: str | None = None

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
    def open_editor_files(self) -> list[OpenFile]:
        """Get open files from editors"""
        return [
            f
            for f in self.open_files
            if f.path.endswith(
                (
                    ".py",
                    ".js",
                    ".ts",
                    ".jsx",
                    ".tsx",
                    ".java",
                    ".cs",
                    ".go",
                    ".rs",
                    ".md",
                )
            )
        ]

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
        summary_parts.append(
            f"Window: {state.active_window.title} ({state.active_window.app_name})"
        )

    # Current project
    if state.current_project:
        summary_parts.append(f"Project: {state.current_project.name}")
        if state.current_project.git_repo:
            summary_parts.append(f"  - Branch: {state.current_project.git_repo.branch}")
            if state.current_project.git_repo.is_dirty:
                summary_parts.append(
                    f"  - Modified files: {state.current_project.git_repo.modified_files}"
                )

    # Open files
    if state.open_files:
        open_count = len(state.open_files)
        summary_parts.append(f"Open files: {open_count}")

    # Running apps
    if state.running_apps:
        editor_apps = [app for app in state.running_apps if app.is_editor]
        if editor_apps:
            summary_parts.append(
                f"Active editor: {', '.join(set(app.name for app in editor_apps))}"
            )

    return " | ".join(summary_parts)
