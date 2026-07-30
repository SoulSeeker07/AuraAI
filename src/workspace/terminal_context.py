"""
Terminal Context Monitor

Monitors terminal state and provides information about the current terminal.

Features:
- Detect terminal type (PowerShell, CMD, WSL, Git Bash)
- Get current working directory
- Track running commands
- Get current command
- Get last command output
"""

import logging
import os
import psutil
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

from .models import TerminalContext, TerminalType

logger = logging.getLogger(__name__)


@dataclass
class TerminalContextMonitor:
    """
    Monitor terminal state.

    Provides:
    - Terminal type detection
    - Working directory information
    - Running command tracking
    """

    def __init__(self):
        """Initialize terminal context monitor"""
        self._current_command: Optional[str] = None
        self._last_command_output: Optional[str] = None
        self._running_commands: List[str] = []
        self._terminal_context: Optional[TerminalContext] = None

        logger.info("Terminal context monitor initialized")

    async def get_terminal_context(self) -> Optional[TerminalContext]:
        """
        Get current terminal context.

        Returns:
            TerminalContext object or None if not in terminal
        """
        try:
            # Get current process
            current_process = psutil.Process()

            # Determine terminal type
            terminal_type = self._detect_terminal_type(current_process)

            # Get working directory
            working_directory = self._get_working_directory(current_process)

            # Check if it's a terminal
            if terminal_type == TerminalType.UNKNOWN:
                return None

            # Create terminal context
            terminal = TerminalContext(
                type=terminal_type,
                working_directory=working_directory,
                running_commands=self._running_commands.copy(),
                current_command=self._current_command,
                last_command_output=self._last_command_output
            )

            self._terminal_context = terminal

            logger.debug(f"Terminal context: {terminal_type.value} @ {working_directory}")

            return terminal

        except Exception as e:
            logger.error(f"Failed to get terminal context: {e}")
            return None

    def _detect_terminal_type(self, process: psutil.Process) -> TerminalType:
        """
        Detect terminal type from process.

        Args:
            process: Current process

        Returns:
            TerminalType
        """
        try:
            exe = process.exe()
            name = process.name()

            if not exe:
                return TerminalType.UNKNOWN

            exe_lower = exe.lower()
            name_lower = name.lower()

            # Check for WSL
            if 'wsl' in exe_lower or 'wsl.exe' in exe_lower:
                return TerminalType.WSL

            # Check for Git Bash
            if 'git-bash' in exe_lower or 'gitbash' in exe_lower:
                return TerminalType.GIT_BASH

            # Check for PowerShell
            if 'powershell' in exe_lower:
                if 'ise' in exe_lower:
                    return TerminalType.POWERSHELL
                return TerminalType.POWERSHELL

            # Check for CMD
            if 'cmd.exe' in exe_lower or name_lower == 'cmd.exe':
                return TerminalType.CMD

            return TerminalType.UNKNOWN

        except Exception as e:
            logger.debug(f"Failed to detect terminal type: {e}")
            return TerminalType.UNKNOWN

    def _get_working_directory(self, process: psutil.Process) -> str:
        """
        Get working directory from process.

        Args:
            process: Current process

        Returns:
            Working directory path
        """
        try:
            cwd = process.cwd()
            if cwd:
                return str(Path(cwd).resolve())

            # Fall back to current directory
            return str(Path.cwd().resolve())

        except Exception as e:
            logger.debug(f"Failed to get working directory: {e}")
            return str(Path.cwd().resolve())

    def set_current_command(self, command: str):
        """
        Set the current running command.

        Args:
            command: Command string
        """
        self._current_command = command
        logger.debug(f"Current command set: {command}")

    def set_command_output(self, output: str):
        """
        Set the output from the last command.

        Args:
            output: Command output string
        """
        self._last_command_output = output
        logger.debug(f"Command output set ({len(output)} chars)")

    def add_running_command(self, command: str):
        """
        Add a running command to the list.

        Args:
            command: Command string
        """
        self._running_commands.append(command)
        # Keep only last 10 commands
        if len(self._running_commands) > 10:
            self._running_commands = self._running_commands[-10:]
        logger.debug(f"Added running command: {command}")

    def clear_running_commands(self):
        """Clear all running commands"""
        self._running_commands = []
        self._current_command = None
        self._last_command_output = None
        logger.debug("Running commands cleared")

    def is_wsl(self) -> bool:
        """
        Check if running in WSL.

        Returns:
            True if in WSL
        """
        return self._terminal_context is not None and self._terminal_context.is_wsl()

    async def get_terminal_type(self) -> Optional[TerminalType]:
        """
        Get terminal type.

        Returns:
            TerminalType or None
        """
        try:
            context = await self.get_terminal_context()
            return context.type if context else None
        except Exception as e:
            logger.error(f"Failed to get terminal type: {e}")
            return None

    async def get_working_directory(self) -> Optional[str]:
        """
        Get working directory.

        Returns:
            Working directory path or None
        """
        try:
            context = await self.get_terminal_context()
            return context.working_directory if context else None
        except Exception as e:
            logger.error(f"Failed to get working directory: {e}")
            return None

    async def get_current_command(self) -> Optional[str]:
        """
        Get current running command.

        Returns:
            Current command or None
        """
        return self._current_command

    async def get_running_commands(self) -> List[str]:
        """
        Get list of running commands.

        Returns:
            List of running commands
        """
        return self._running_commands.copy()

    def cleanup(self):
        """Clean up resources"""
        self.clear_running_commands()


# Singleton instance
_terminal_monitor = TerminalContextMonitor()


def get_terminal_monitor() -> TerminalContextMonitor:
    """
    Get the terminal monitor singleton.

    Returns:
        TerminalContextMonitor instance
    """
    return _terminal_monitor
