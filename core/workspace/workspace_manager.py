"""
Workspace Manager

Manages workspace context and desktop operations.
Provides information about the current environment.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """
    Manages workspace context.
    
    Responsibilities:
        - Track current directory
        - Provide git repository information
        - Handle clipboard operations
        - Manage running processes
        - Track active window
        - Provide provider settings
    
    This gives Aura awareness of the user's environment.
    """
    
    def __init__(self, root_path: Optional[Path] = None):
        """
        Initialize Workspace Manager.
        
        Args:
            root_path: Root path for workspace operations
        """
        self.root_path = root_path or Path.cwd()
        self.current_directory: Path = self.root_path
        self._git_repo: Optional[Path] = None
        self._clipboard: Optional[str] = None
        self._running_processes: Optional[list] = None
        self._active_window: Optional[dict] = None
        
        # Check if we're in a git repository
        self._check_git_repository()
        
        logger.info(f"Workspace Manager initialized at: {self.root_path}")
    
    @property
    def current_directory(self) -> Path:
        """Get current working directory."""
        return self._current_directory
    
    @current_directory.setter
    def current_directory(self, value: Path):
        """Set current working directory."""
        self._current_directory = value
        self._check_git_repository()
        logger.debug(f"Current directory changed to: {value}")
    
    def get_git_repo(self) -> Optional[str]:
        """
        Get current git repository information.
        
        Returns:
            Git repository path or None
        """
        return str(self._git_repo) if self._git_repo else None
    
    def _check_git_repository(self):
        """Check if we're in a git repository."""
        try:
            import subprocess
            
            result = subprocess.run(
                ['git', 'rev-parse', '--show-toplevel'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                self._git_repo = Path(result.stdout.strip())
                logger.debug(f"Git repository detected: {self._git_repo}")
            else:
                self._git_repo = None
        
        except Exception as e:
            logger.warning(f"Could not check git repository: {e}")
            self._git_repo = None
    
    def get_clipboard(self) -> Optional[str]:
        """
        Get clipboard content.
        
        Returns:
            Clipboard content or None
        """
        return self._clipboard
    
    def set_clipboard(self, content: str):
        """
        Set clipboard content.
        
        Args:
            content: Content to set
        """
        self._clipboard = content
        logger.debug(f"Clipboard updated")
    
    def get_running_processes(self) -> list[str]:
        """
        Get list of running processes.
        
        Returns:
            List of process names
        """
        if self._running_processes is None:
            try:
                import psutil
                self._running_processes = [p.name() for p in psutil.process_iter()]
                logger.debug(f"Running processes: {len(self._running_processes)}")
            except ImportError:
                logger.warning("psutil not available, cannot get processes")
                self._running_processes = []
            except Exception as e:
                logger.error(f"Failed to get running processes: {e}")
                self._running_processes = []
        
        return self._running_processes
    
    def get_active_window(self) -> Optional[dict]:
        """
        Get information about active window.
        
        Returns:
            Dictionary with window info or None
        """
        return self._active_window
    
    def set_active_window(self, window_info: dict):
        """
        Set active window information.
        
        Args:
            window_info: Window information dictionary
        """
        self._active_window = window_info
        logger.debug(f"Active window set: {window_info.get('title', 'Unknown')}")
    
    def change_directory(self, directory: str | Path):
        """
        Change current directory.
        
        Args:
            directory: New directory path
        """
        new_dir = Path(directory)
        
        if not new_dir.exists():
            logger.warning(f"Directory does not exist: {new_dir}")
            return
        
        self.current_directory = new_dir
        logger.info(f"Changed directory to: {new_dir}")
    
    def get_provider_settings(self) -> dict[str, Any]:
        """
        Get provider settings.
        
        Returns:
            Dictionary of provider settings
        """
        return {
            'default_provider': 'groq',
            'temperature': 0.7,
            'max_tokens': 1024,
            'enable_streaming': True,
            'context_window': 4096,
            'models': {
                'groq': 'llama3-8b-8192',
                'gemini': 'gemini-pro',
                'ollama': 'llama2'
            }
        }
    
    def get_workspace_summary(self) -> dict[str, Any]:
        """
        Get comprehensive workspace summary.
        
        Returns:
            Dictionary with workspace information
        """
        return {
            'current_directory': str(self.current_directory),
            'git_repository': self.get_git_repo(),
            'root_path': str(self.root_path),
            'timestamp': datetime.now().isoformat(),
            'clipboard': self.get_clipboard(),
            'running_processes': self.get_running_processes(),
            'active_window': self.get_active_window(),
            'provider_settings': self.get_provider_settings()
        }
    
    def reset(self):
        """Reset workspace state."""
        self._running_processes = None
        self._active_window = None
        logger.debug("Workspace state reset")
