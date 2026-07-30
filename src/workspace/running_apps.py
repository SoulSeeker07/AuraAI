"""
Running Applications Monitor

Monitors running applications on the system.

Features:
- List all running applications
- Identify foreground (active) application
- Filter by app type (editor, browser, etc.)
- Track app names and process names
"""

import logging
from typing import List, Optional
from dataclasses import dataclass
import psutil

from .models import RunningApplication

logger = logging.getLogger(__name__)


class RunningAppsMonitor:
    """
    Monitor running applications.

    Provides:
    - List of all running applications
    - Current foreground application
    - App type filtering
    - Process information
    """

    # System processes to exclude
    SYSTEM_PROCESSES = {
        'System',
        'System Idle Process',
        'registry',
        'svchost',
        'spoolsv',
        'alg',
        'csrss',
        'smss',
        'csrss',
        'wininit',
        'services',
        'lsass',
        'lsm',
        'fontdrvhost',
        'tiwinsrv',
        'tiimgtbt',
        'winlogon',
        'dwm',
        'runtimebroker',
        'locationnlp',
        'nlahost',
        'werfault',
        'conhost',
        'vmware',
        'vmtools',
        'vmsrvc',
        'mpcmdrun',
        'sppsvc',
        'wuauserv',
        'audiodg',
        'csrss',
        'smss',
        'wininit',
        'services',
        'lsass',
        'lsass',
        'wininit',
        'services',
    }

    # App name mappings for better UX
    APP_MAPPINGS = {
        'code': 'VS Code',
        'cursor': 'Cursor',
        'atom': 'Atom',
        'sublime_text': 'Sublime Text',
        'pycharm': 'PyCharm',
        'idea': 'IntelliJ IDEA',
        'visual_studio': 'Visual Studio',
        'visual_studio_code': 'VS Code',
        'code.exe': 'VS Code',
        'cursor.exe': 'Cursor',
        'atom.exe': 'Atom',
        'sublime_text.exe': 'Sublime Text',
        'pycharm64.exe': 'PyCharm',
        'idea64.exe': 'IntelliJ IDEA',
        'devenv.exe': 'Visual Studio',
        'powershell.exe': 'Windows Terminal',
        'cmd.exe': 'Command Prompt',
        'powershell_ise.exe': 'Windows PowerShell ISE',
        'node.exe': 'Node.js',
        'python.exe': 'Python',
        'pythonw.exe': 'Python',
        'python3.exe': 'Python',
        'pythonw3.exe': 'Python',
        'google_chrome.exe': 'Chrome',
        'chrome.exe': 'Chrome',
        'msedge.exe': 'Edge',
        'microsoftedge.exe': 'Edge',
        'firefox.exe': 'Firefox',
        'brave.exe': 'Brave',
        'safari.exe': 'Safari',
        'discord.exe': 'Discord',
        'slack.exe': 'Slack',
        'microsoft_teams.exe': 'Teams',
        'outlook.exe': 'Outlook',
        'teamviewer.exe': 'TeamViewer',
        'wireshark.exe': 'Wireshark',
        'packettracer.exe': 'Packet Tracer',
        'vmware.exe': 'VMware',
    }

    # Common editors
    EDITOR_APPS = {
        'vscode', 'cursor', 'code', 'atom', 'sublime', 'pycharm', 'idea',
        'visual_studio', 'visual_studio_code'
    }

    # Common browsers
    BROWSER_APPS = {
        'chrome', 'edge', 'firefox', 'brave', 'safari'
    }

    def __init__(self, update_interval: int = 5):
        """
        Initialize running apps monitor.

        Args:
            update_interval: Seconds between updates
        """
        self.update_interval = update_interval
        self._running_apps: List[RunningApplication] = []
        self._last_foreground_app: Optional[str] = None
        self._foreground_pid: Optional[int] = None
        self._running = False
        self._thread: Optional = None

        logger.info(f"Running apps monitor initialized (update_interval={update_interval}s)")

    async def get_running_apps(self) -> List[RunningApplication]:
        """
        Get list of running applications.

        Returns:
            List of RunningApplication objects
        """
        try:
            apps = self._get_all_processes()
            self._running_apps = apps

            # Set foreground app
            if self._foreground_pid:
                foreground_app = self._get_app_by_pid(self._foreground_pid)
                if foreground_app:
                    foreground_app.is_foreground = True

            return self._running_apps

        except Exception as e:
            logger.error(f"Failed to get running apps: {e}")
            return self._running_apps

    def _get_all_processes(self) -> List[RunningApplication]:
        """
        Get all non-system processes.

        Returns:
            List of RunningApplication objects
        """
        apps = []

        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    # Skip system processes
                    proc_name = proc.info['name']
                    if proc_name in self.SYSTEM_PROCESSES:
                        continue

                    exe_path = proc.info['exe']
                    if not exe_path:
                        continue

                    # Extract process name from path
                    process_name = self._extract_process_name(exe_path)

                    # Create app object
                    app = RunningApplication(
                        name=process_name,
                        process_name=proc_name,
                        window_title=self._get_window_title(proc_name),
                        is_foreground=False
                    )

                    apps.append(app)

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

        except Exception as e:
            logger.error(f"Error iterating processes: {e}")

        return apps

    def _get_app_by_pid(self, pid: int) -> Optional[RunningApplication]:
        """
        Get application by PID.

        Args:
            pid: Process ID

        Returns:
            RunningApplication or None
        """
        for app in self._running_apps:
            if app.pid == pid:
                return app
        return None

    def _extract_process_name(self, exe_path: str) -> str:
        """
        Extract clean process name from executable path.

        Args:
            exe_path: Full path to executable

        Returns:
            Clean process name
        """
        # Get basename
        basename = exe_path.split('\\')[-1].split('/')[-1]

        # Check mappings
        basename_lower = basename.lower()
        if basename_lower in self.APP_MAPPINGS:
            return self.APP_MAPPINGS[basename_lower]

        # Clean up the name
        return basename.replace('.exe', '')

    def _get_window_title(self, process_name: str) -> str:
        """
        Get window title for a process.

        Args:
            process_name: Process name

        Returns:
            Window title or empty string
        """
        try:
            # For now, return empty string (would need Windows API to get window titles)
            return ""
        except Exception:
            return ""

    async def get_foreground_app(self) -> Optional[RunningApplication]:
        """
        Get the currently foreground application.

        Returns:
            RunningApplication for foreground app or None
        """
        try:
            # Set current foreground PID
            self._foreground_pid = psutil.Process().ppid()

            # Get all apps
            apps = await self.get_running_apps()

            # Find foreground app
            for app in apps:
                if app.pid == self._foreground_pid:
                    self._last_foreground_app = app.name
                    return app

            return None

        except Exception as e:
            logger.error(f"Failed to get foreground app: {e}")
            return None

    async def get_app_by_name(self, name: str) -> Optional[RunningApplication]:
        """
        Get application by name.

        Args:
            name: Application name

        Returns:
            RunningApplication or None
        """
        try:
            apps = await self.get_running_apps()
            for app in apps:
                if app.name.lower() == name.lower():
                    return app
            return None

        except Exception as e:
            logger.error(f"Failed to get app by name: {e}")
            return None

    async def get_editor_apps(self) -> List[RunningApplication]:
        """
        Get all running editor applications.

        Returns:
            List of editor applications
        """
        try:
            apps = await self.get_running_apps()
            return [app for app in apps if app.is_editor]

        except Exception as e:
            logger.error(f"Failed to get editor apps: {e}")
            return []

    async def get_browser_apps(self) -> List[RunningApplication]:
        """
        Get all running browser applications.

        Returns:
            List of browser applications
        """
        try:
            apps = await self.get_running_apps()
            return [app for app in apps if app.is_browser]

        except Exception as e:
            logger.error(f"Failed to get browser apps: {e}")
            return []

    def get_foreground_app_name(self) -> Optional[str]:
        """
        Get name of foreground application.

        Returns:
            Foreground app name or None
        """
        return self._last_foreground_app

    def start_monitoring(self):
        """Start monitoring running apps"""
        if self._running:
            return

        self._running = True
        # Monitoring is event-based, no background thread needed

        logger.info("Running apps monitoring started")

    def stop_monitoring(self):
        """Stop monitoring running apps"""
        self._running = False
        logger.info("Running apps monitoring stopped")

    def cleanup(self):
        """Clean up resources"""
        self.stop_monitoring()
        self._running_apps = []
        self._last_foreground_app = None
        self._foreground_pid = None
