"""
Workspace Manager

Single source of truth for desktop context awareness.
Aggregates information from all workspace sensors.
"""

import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import asyncio
import psutil

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

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """
    Main orchestrator for workspace awareness.

    Provides a unified interface to access all desktop context information.
    All modules should query this manager, not access Windows directly.
    """

    def __init__(
        self,
        data_path: Optional[Path] = None,
        update_interval: int = 5,
        enabled_features: Optional[dict] = None
    ):
        """
        Initialize Workspace Manager.

        Args:
            data_path: Path to store workspace state
            update_interval: Seconds between automatic updates
            enabled_features: Dictionary of enabled features (clipboard, git, etc.)
        """
        self.data_path = data_path or Path("Data/workspace_state.json")
        self.update_interval = update_interval
        self.enabled_features = enabled_features or {
            'active_window': True,
            'project_detection': True,
            'git': True,
            'clipboard': False,  # Disabled by default for privacy
            'running_apps': True,
            'terminal': False,
            'browser': False
        }

        # Initialize state
        self.state = WorkspaceState(
            platform=PlatformType.WINDOWS
        )

        # Load from disk
        self._load_state()

        # Initialize sensors
        self._sensors = {}
        self._start_sensors()

        logger.info(f"Workspace Manager initialized with features: {list(self.enabled_features.keys())}")

    def _start_sensors(self):
        """Start all enabled sensors"""
        if self.enabled_features.get('active_window'):
            from .active_window import ActiveWindowMonitor
            self._sensors['active_window'] = ActiveWindowMonitor()

        if self.enabled_features.get('project_detection'):
            from .project_detector import ProjectDetector
            self._sensors['project'] = ProjectDetector()

        if self.enabled_features.get('git'):
            from .git_context import GitContext
            self._sensors['git'] = GitContext()

        if self.enabled_features.get('clipboard'):
            from .clipboard_monitor import ClipboardMonitor
            self._sensors['clipboard'] = ClipboardMonitor()

        if self.enabled_features.get('running_apps'):
            from .running_apps import RunningAppsMonitor
            self._sensors['running_apps'] = RunningAppsMonitor()

        if self.enabled_features.get('terminal'):
            from .terminal_context import TerminalContextMonitor
            self._sensors['terminal'] = TerminalContextMonitor()

    async def update(self):
        """Update all workspace state"""
        logger.debug("Updating workspace state...")

        # Update active window
        if 'active_window' in self._sensors:
            try:
                window = await self._sensors['active_window'].get_active_window()
                self.state.active_window = window
            except Exception as e:
                logger.warning(f"Failed to get active window: {e}")

        # Update project detection
        if 'project' in self._sensors:
            try:
                project = await self._sensors['project'].detect_current_project()
                self.state.current_project = project
                if project:
                    self.state.workspace_folder = project.path
            except Exception as e:
                logger.warning(f"Failed to detect project: {e}")

        # Update git context
        if 'git' in self._sensors and self.enabled_features.get('git'):
            try:
                git_repo = await self._sensors['git'].get_git_repo()
                if git_repo:
                    self.state.git_repo = git_repo
                    if self.state.current_project and self.state.current_project.git_repo is None:
                        self.state.current_project.git_repo = git_repo
            except Exception as e:
                logger.warning(f"Failed to get git context: {e}")

        # Update clipboard
        if 'clipboard' in self._sensors and self.enabled_features.get('clipboard'):
            try:
                clipboard = await self._sensors['clipboard'].get_clipboard()
                self.state.clipboard = clipboard
            except Exception as e:
                logger.warning(f"Failed to get clipboard: {e}")

        # Update running apps
        if 'running_apps' in self._sensors:
            try:
                apps = await self._sensors['running_apps'].get_running_apps()
                self.state.running_apps = apps
            except Exception as e:
                logger.warning(f"Failed to get running apps: {e}")

        # Update terminal
        if 'terminal' in self._sensors and self.enabled_features.get('terminal'):
            try:
                terminal = await self._sensors['terminal'].get_terminal_context()
                self.state.terminal = terminal
            except Exception as e:
                logger.warning(f"Failed to get terminal context: {e}")

        # Update browser
        if 'browser' in self._sensors and self.enabled_features.get('browser'):
            try:
                browser = await self._sensors['browser'].get_browser_context()
                self.state.browser = browser
            except Exception as e:
                logger.warning(f"Failed to get browser context: {e}")

        # Update timestamp
        self.state.update_timestamp()

        # Save to disk
        self._save_state()

        logger.debug(f"Workspace state updated: {len(self.state.open_files)} open files")

    async def force_update(self):
        """Force an immediate update (ignore interval)"""
        await self.update()

    async def update_project(self, project_path: Optional[str] = None):
        """
        Update workspace with specific project.

        Args:
            project_path: Optional path to project. If None, auto-detects.
        """
        if 'project' in self._sensors:
            try:
                project = await self._sensors['project'].detect_current_project(project_path)
                self.state.current_project = project
                if project:
                    self.state.workspace_folder = project.path
                self._save_state()
            except Exception as e:
                logger.warning(f"Failed to update project: {e}")

    async def add_open_file(self, file_path: str, modified: bool = False):
        """
        Add or update an open file.

        Args:
            file_path: Path to the file
            modified: Whether file has been modified
        """
        file_path = str(Path(file_path).resolve())

        # Remove existing entry if any
        self.state.open_files = [
            f for f in self.state.open_files if f.path != file_path
        ]

        # Add new entry
        open_file = OpenFile(
            path=file_path,
            name=Path(file_path).name,
            modified=modified,
            last_accessed=datetime.now()
        )

        self.state.open_files.append(open_file)

        # Update recent files
        self.state.recent_files.insert(0, file_path)
        self.state.recent_files = self.state.recent_files[:50]  # Keep last 50

        # Update modified files
        if modified:
            self.state.modified_files.append(file_path)

        # Update timestamp
        self.state.update_timestamp()

        logger.debug(f"Added open file: {file_path}")

    async def mark_file_modified(self, file_path: str):
        """
        Mark a file as modified.

        Args:
            file_path: Path to the file
        """
        await self.add_open_file(file_path, modified=True)

    async def remove_open_file(self, file_path: str):
        """
        Remove a file from open files.

        Args:
            file_path: Path to the file
        """
        file_path = str(Path(file_path).resolve())
        self.state.open_files = [
            f for f in self.state.open_files if f.path != file_path
        ]
        logger.debug(f"Removed open file: {file_path}")

    async def set_clipboard(self, content: str, is_code: bool = False):
        """
        Manually set clipboard content.

        Args:
            content: Clipboard content
            is_code: Whether content is code
        """
        self.state.clipboard = ClipboardContext(
            text=content,
            code=content if is_code else None,
            is_code=is_code,
            is_text=True
        )
        self.state.update_timestamp()

    def get_state(self) -> WorkspaceState:
        """
        Get the current workspace state.

        Returns:
            WorkspaceState object
        """
        return self.state

    def get_context_summary(self) -> str:
        """
        Get a human-readable summary of workspace state.

        Returns:
            String summary of current context
        """
        return self.state.get_context_summary()

    def is_feature_enabled(self, feature: str) -> bool:
        """
        Check if a feature is enabled.

        Args:
            feature: Feature name

        Returns:
            True if enabled
        """
        return self.enabled_features.get(feature, False)

    def enable_feature(self, feature: str, enabled: bool = True):
        """
        Enable or disable a feature.

        Args:
            feature: Feature name
            enabled: Whether to enable (True) or disable (False)
        """
        if feature in self.enabled_features:
            self.enabled_features[feature] = enabled
            logger.info(f"Feature '{feature}' set to {enabled}")

    def _save_state(self):
        """Save workspace state to disk"""
        try:
            # Ensure directory exists
            self.data_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert to serializable format
            state_dict = {
                'platform': self.state.platform.value,
                'active_window': None,
                'current_project': None,
                'workspace_folder': self.state.workspace_folder,
                'open_files': [],
                'recent_files': [],
                'pinned_files': [],
                'modified_files': [],
                'git_repo': None,
                'terminal': None,
                'clipboard': None,
                'running_apps': [],
                'browser': None,
                'last_updated': self.state.last_updated.isoformat(),
                'workspace_folder_path': self.state.workspace_folder_path
            }

            # Convert enums to strings
            if self.state.active_window:
                state_dict['active_window'] = {
                    'title': self.state.active_window.title,
                    'app_name': self.state.active_window.app_name,
                    'process_name': self.state.active_window.process_name
                }

            if self.state.current_project:
                state_dict['current_project'] = {
                    'path': self.state.current_project.path,
                    'name': self.state.current_project.name,
                    'type': self.state.current_project.type.value
                }

            if self.state.git_repo:
                state_dict['git_repo'] = {
                    'path': self.state.git_repo.path,
                    'branch': self.state.git_repo.branch,
                    'remote_url': self.state.git_repo.remote_url,
                    'commit_hash': self.state.git_repo.commit_hash,
                    'modified_files': self.state.git_repo.modified_files,
                    'is_dirty': self.state.git_repo.is_dirty
                }

            if self.state.clipboard:
                state_dict['clipboard'] = {
                    'text': self.state.clipboard.text,
                    'is_code': self.state.clipboard.is_code,
                    'timestamp': self.state.clipboard.timestamp.isoformat()
                }

            if self.state.running_apps:
                state_dict['running_apps'] = [
                    {
                        'name': app.name,
                        'process_name': app.process_name,
                        'is_foreground': app.is_foreground
                    }
                    for app in self.state.running_apps
                ]

            # Convert datetime to isoformat
            state_dict['last_updated'] = self.state.last_updated.isoformat()
            if self.state.clipboard:
                state_dict['clipboard']['timestamp'] = self.state.clipboard.timestamp.isoformat()

            # Save to file
            import json
            with open(self.data_path, 'w') as f:
                json.dump(state_dict, f, indent=2)

            logger.debug(f"Saved workspace state to {self.data_path}")

        except Exception as e:
            logger.error(f"Failed to save workspace state: {e}")

    def _load_state(self):
        """Load workspace state from disk"""
        try:
            if not self.data_path.exists():
                logger.debug("Workspace state file not found, starting fresh")
                return

            import json
            with open(self.data_path, 'r') as f:
                state_dict = json.load(f)

            # Convert back from serializable format
            self.state = WorkspaceState(
                platform=PlatformType(state_dict.get('platform', 'windows')),
                workspace_folder_path=state_dict.get('workspace_folder_path')
            )

            # Restore active_window
            if state_dict.get('active_window'):
                active_window_data = state_dict['active_window']
                self.state.active_window = ActiveWindow(
                    title=active_window_data['title'],
                    app_name=active_window_data['app_name'],
                    process_name=active_window_data['process_name']
                )

            # Restore current_project
            if state_dict.get('current_project'):
                project_data = state_dict['current_project']
                self.state.current_project = CurrentProject(
                    path=project_data['path'],
                    name=project_data['name'],
                    type=ProjectType(project_data.get('type', 'unknown'))
                )

            # Restore git_repo
            if state_dict.get('git_repo'):
                git_data = state_dict['git_repo']
                self.state.git_repo = GitRepository(
                    path=git_data['path'],
                    branch=git_data['branch'],
                    remote_url=git_data.get('remote_url'),
                    commit_hash=git_data.get('commit_hash'),
                    modified_files=git_data.get('modified_files', []),
                    is_dirty=git_data.get('is_dirty', False)
                )

            # Restore clipboard
            if state_dict.get('clipboard'):
                clipboard_data = state_dict['clipboard']
                self.state.clipboard = ClipboardContext(
                    text=clipboard_data.get('text'),
                    is_code=clipboard_data.get('is_code', False),
                    timestamp=datetime.fromisoformat(clipboard_data['timestamp'])
                )

            # Restore running_apps
            if state_dict.get('running_apps'):
                self.state.running_apps = [
                    RunningApplication(
                        name=app['name'],
                        process_name=app['process_name'],
                        is_foreground=app.get('is_foreground', False)
                    )
                    for app in state_dict['running_apps']
                ]

            # Restore datetime
            self.state.last_updated = datetime.fromisoformat(state_dict['last_updated'])
            if self.state.clipboard:
                self.state.clipboard.timestamp = datetime.fromisoformat(clipboard_data['timestamp'])

            logger.info(f"Loaded workspace state from {self.data_path}")

        except Exception as e:
            logger.error(f"Failed to load workspace state: {e}")
            # Start with empty state
            self.state = WorkspaceState(platform=PlatformType.WINDOWS)

    def cleanup(self):
        """Clean up resources"""
        # Close sensors
        for sensor in self._sensors.values():
            if hasattr(sensor, 'cleanup'):
                sensor.cleanup()

        logger.info("Workspace Manager cleaned up")
