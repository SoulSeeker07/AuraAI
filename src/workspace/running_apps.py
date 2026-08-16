"""
Running Applications Monitor
Location: src/workspace/running_apps.py

Monitors running applications on the system.
Features:
- List all running non-system applications
- Accurately identify foreground application by delegating to ActiveWindowMonitor
- Filter by app type (editor, browser, etc.)
- Provides both synchronous and non-blocking asynchronous APIs
"""

import asyncio
import logging
from typing import Optional

import psutil

from .active_window import ActiveWindowMonitor
from .models import RunningApplication

logger = logging.getLogger(__name__)


class RunningAppsMonitor:
    """
    Monitor running applications.

    Provides:
    - List of all running applications
    - Current foreground application (via ActiveWindowMonitor)
    - App type filtering
    - Process information
    """

    # System processes to exclude from user application lists
    SYSTEM_PROCESSES = {
        "System",
        "System Idle Process",
        "registry",
        "svchost",
        "spoolsv",
        "alg",
        "csrss",
        "smss",
        "wininit",
        "services",
        "lsass",
        "lsm",
        "fontdrvhost",
        "tiwinsrv",
        "tiimgtbt",
        "winlogon",
        "dwm",
        "runtimebroker",
        "locationnlp",
        "nlahost",
        "werfault",
        "conhost",
        "vmware",
        "vmtools",
        "vmsrvc",
        "mpcmdrun",
        "sppsvc",
        "wuauserv",
        "audiodg",
    }

    # App name mappings for UX display
    APP_MAPPINGS = {
        "code": "VS Code",
        "cursor": "Cursor",
        "atom": "Atom",
        "sublime_text": "Sublime Text",
        "pycharm": "PyCharm",
        "idea": "IntelliJ IDEA",
        "visual_studio": "Visual Studio",
        "visual_studio_code": "VS Code",
        "code.exe": "VS Code",
        "cursor.exe": "Cursor",
        "atom.exe": "Atom",
        "sublime_text.exe": "Sublime Text",
        "pycharm64.exe": "PyCharm",
        "idea64.exe": "IntelliJ IDEA",
        "devenv.exe": "Visual Studio",
        "powershell.exe": "Windows Terminal",
        "cmd.exe": "Command Prompt",
        "powershell_ise.exe": "Windows PowerShell ISE",
        "node.exe": "Node.js",
        "python.exe": "Python",
        "pythonw.exe": "Python",
        "python3.exe": "Python",
        "pythonw3.exe": "Python",
        "google_chrome.exe": "Chrome",
        "chrome.exe": "Chrome",
        "msedge.exe": "Edge",
        "microsoftedge.exe": "Edge",
        "firefox.exe": "Firefox",
        "brave.exe": "Brave",
        "safari.exe": "Safari",
        "discord.exe": "Discord",
        "slack.exe": "Slack",
        "microsoft_teams.exe": "Teams",
        "outlook.exe": "Outlook",
        "teamviewer.exe": "TeamViewer",
        "wireshark.exe": "Wireshark",
        "packettracer.exe": "Packet Tracer",
        "vmware.exe": "VMware",
    }

    EDITOR_APPS = {
        "vscode",
        "cursor",
        "code",
        "atom",
        "sublime",
        "pycharm",
        "idea",
        "visual_studio",
        "visual_studio_code",
    }

    BROWSER_APPS = {"chrome", "edge", "firefox", "brave", "safari"}

    def __init__(self, update_interval: int = 5, window_monitor: ActiveWindowMonitor | None = None):
        """
        Initialize running apps monitor.

        Args:
            update_interval: Seconds between updates
            window_monitor: Optional ActiveWindowMonitor instance
        """
        self.update_interval = update_interval
        self.window_monitor = window_monitor or ActiveWindowMonitor()
        self._running_apps: list[RunningApplication] = []
        self._last_foreground_app: str | None = None
        self._foreground_pid: int | None = None
        self._running = False

    def get_running_apps_sync(self) -> list[RunningApplication]:
        """
        Synchronously get list of running applications with foreground status marked.

        Returns:
            List of RunningApplication objects
        """
        try:
            # Query true OS foreground window
            active_win = self.window_monitor.get_active_window_sync()
            fg_pid = None
            fg_title = ""
            if active_win:
                # Find PID if available or window title
                fg_title = active_win.title
                self._last_foreground_app = active_win.app_name

            apps: list[RunningApplication] = []
            for proc in psutil.process_iter(["pid", "name", "exe"]):
                try:
                    proc_name = proc.info.get("name") or ""
                    if proc_name in self.SYSTEM_PROCESSES or proc_name.lower() in self.SYSTEM_PROCESSES:
                        continue

                    exe_path = proc.info.get("exe") or ""
                    if not exe_path and not proc_name:
                        continue

                    clean_name = self._extract_process_name(exe_path or proc_name)
                    pid = proc.info.get("pid")
                    
                    is_fg = False
                    window_title = ""
                    if active_win and active_win.process_name and (
                        active_win.process_name.lower() == proc_name.lower()
                        or (pid and getattr(active_win, "rect", None) and pid == self._get_pid_from_hwnd(active_win.window_id))
                    ):
                        is_fg = True
                        window_title = fg_title

                    app = RunningApplication(
                        name=clean_name,
                        process_name=proc_name.replace(".exe", "").lower(),
                        window_title=window_title,
                        is_foreground=is_fg,
                        pid=pid,
                    )
                    apps.append(app)

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

            self._running_apps = apps
            return self._running_apps

        except Exception as e:
            logger.error(f"Failed to get running apps: {e}")
            return self._running_apps

    def _get_pid_from_hwnd(self, hwnd: int | None) -> int | None:
        """Helper to extract PID from window handle if available."""
        if not hwnd:
            return None
        try:
            import ctypes
            pid = ctypes.c_uint(0)
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return pid.value
        except Exception:
            return None

    async def get_running_apps(self) -> list[RunningApplication]:
        """
        Asynchronously get list of running applications without blocking the event loop.
        """
        return await asyncio.to_thread(self.get_running_apps_sync)

    def get_foreground_app_sync(self) -> RunningApplication | None:
        """
        Synchronously get the currently foreground application.
        """
        active_win = self.window_monitor.get_active_window_sync()
        if not active_win:
            return None

        self._last_foreground_app = active_win.app_name
        return RunningApplication(
            name=active_win.app_name,
            process_name=active_win.process_name.replace(".exe", "").lower(),
            window_title=active_win.title,
            is_foreground=True,
        )

    async def get_foreground_app(self) -> RunningApplication | None:
        """
        Asynchronously get the currently foreground application without blocking.
        """
        return await asyncio.to_thread(self.get_foreground_app_sync)

    def _extract_process_name(self, exe_path: str) -> str:
        """Extract clean application name from executable path or name."""
        basename = exe_path.split("\\")[-1].split("/")[-1]
        basename_lower = basename.lower()
        if basename_lower in self.APP_MAPPINGS:
            return self.APP_MAPPINGS[basename_lower]
        return basename.replace(".exe", "")

    async def get_app_by_name(self, name: str) -> RunningApplication | None:
        """Get application by name."""
        apps = await self.get_running_apps()
        for app in apps:
            if app.name.lower() == name.lower() or app.process_name.lower() == name.lower():
                return app
        return None

    async def get_editor_apps(self) -> list[RunningApplication]:
        """Get all running editor applications."""
        apps = await self.get_running_apps()
        return [app for app in apps if app.is_editor]

    async def get_browser_apps(self) -> list[RunningApplication]:
        """Get all running browser applications."""
        apps = await self.get_running_apps()
        return [app for app in apps if app.is_browser]

    def get_foreground_app_name(self) -> str | None:
        """Get name of last known foreground application."""
        return self._last_foreground_app

    def start_monitoring(self):
        """Start monitoring running apps."""
        self._running = True

    def stop_monitoring(self):
        """Stop monitoring running apps."""
        self._running = False

    def cleanup(self):
        """Clean up resources."""
        self.stop_monitoring()
        self._running_apps = []
        self._last_foreground_app = None
        self._foreground_pid = None
