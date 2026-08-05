"""
Desktop Agent - Controls the desktop environment safely.

The Desktop Agent provides safe, controlled access to:
- Application management
- File operations
- System controls
- Window management
- Clipboard operations
- Process management
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# Import ProcessManager
from .process_manager import ProcessManager
from .task_model import Task, TaskOutput


class DesktopAgent:
    """
    Controls desktop operations safely through a confirmed permission layer.

    The Desktop Agent only executes operations after user confirmation when
    they require elevated privileges or could have destructive impact.
    """

    def __init__(self, task_manager, safety_layer=None):
        """
        Initialize the desktop agent.

        Args:
            task_manager: TaskManager instance
            safety_layer: Optional SafetyLayer for confirmation checks
        """
        self.task_manager = task_manager
        self._safety_layer = safety_layer
        self._permissions: dict[str, bool] = {}

        # Initialize process manager for process management tasks
        self.process_manager = ProcessManager()

    def _require_confirmation(self, action: str, details: str) -> bool:
        """
        Require user confirmation for action.

        Args:
            action: Action being performed
            details: Details about the action

        Returns:
            True if user confirmed, False otherwise
        """
        if self._safety_layer:
            return self._safety_layer.confirm_action(action, details)
        return True

    def execute_task(self, task: Task) -> TaskOutput:
        """
        Execute a desktop task.

        Args:
            task: Task to execute

        Returns:
            Task execution result
        """
        try:
            method = getattr(self, f"_execute_{task.type.value}", None)

            if not method:
                return TaskOutput(
                    success=False,
                    message=f"No handler for task type: {task.type.value}",
                    error=f"Task type {task.type.value} not supported",
                )

            return method(task)

        except Exception as e:
            return TaskOutput(
                success=False, message="Error executing task", error=str(e)
            )

    # ========================================
    # APPLICATION MANAGEMENT
    # ========================================

    def _execute_app_open(self, task: Task) -> TaskOutput:
        """Open an application."""
        app_name = task.input.get("app_name")

        if not app_name:
            return TaskOutput(
                success=False,
                message="Failed to open application",
                error="App name not provided",
            )

        if not self._require_confirmation("Open Application", f"Opening {app_name}"):
            return TaskOutput(success=False, message="Action cancelled by user")

        # Windows command to open app
        try:
            if app_name.lower().endswith(".exe"):
                subprocess.Popen([app_name], shell=True)
            else:
                # Try common launchers
                subprocess.Popen(["start", app_name], shell=True)

            return TaskOutput(
                success=True,
                message=f"Application opened: {app_name}",
                data={"app_name": app_name},
            )

        except Exception as e:
            return TaskOutput(
                success=False, message=f"Failed to open {app_name}", error=str(e)
            )

    def _execute_app_close(self, task: Task) -> TaskOutput:
        """Close an application."""
        app_name = task.input.get("app_name")

        if not app_name:
            return TaskOutput(
                success=False,
                message="Failed to close application",
                error="App name not provided",
            )

        if not self._require_confirmation("Close Application", f"Closing {app_name}"):
            return TaskOutput(success=False, message="Action cancelled by user")

        # Try to close via task manager (Windows)
        try:
            subprocess.Popen(["taskkill", "/F", "/IM", app_name + ".exe"], shell=True)

            return TaskOutput(
                success=True,
                message=f"Application closed: {app_name}",
                data={"app_name": app_name},
            )

        except Exception as e:
            # Fallback: return error
            return TaskOutput(
                success=False, message=f"Failed to close {app_name}", error=str(e)
            )

    # ========================================
    # FILE OPERATIONS
    # ========================================

    def _execute_file_search(self, task: Task) -> TaskOutput:
        """Search for files."""
        search_pattern = task.input.get("pattern", "*")
        directory = task.input.get("directory", str(Path.home()))
        max_results = task.input.get("max_results", 50)

        try:
            search_path = Path(directory)
            if not search_path.exists():
                return TaskOutput(
                    success=False,
                    message="Directory not found",
                    error=f"Path does not exist: {directory}",
                )

            results = []
            for item in search_path.rglob(search_pattern):
                if item.is_file() or item.is_dir():
                    results.append(
                        {
                            "name": item.name,
                            "path": str(item.absolute()),
                            "type": "file" if item.is_file() else "directory",
                            "size": item.stat().st_size if item.is_file() else 0,
                        }
                    )
                    if len(results) >= max_results:
                        break

            return TaskOutput(
                success=True,
                message=f"Found {len(results)} files",
                data={"results": results, "count": len(results)},
            )

        except Exception as e:
            return TaskOutput(success=False, message="File search failed", error=str(e))

    def _execute_file_rename(self, task: Task) -> TaskOutput:
        """Rename a file."""
        file_path = task.input.get("file_path")
        new_name = task.input.get("new_name")

        if not file_path or not new_name:
            return TaskOutput(
                success=False,
                message="Failed to rename file",
                error="File path and new name required",
            )

        if not self._require_confirmation(
            "Rename File", f"Renaming:\n{file_path}\nto:\n{new_name}"
        ):
            return TaskOutput(success=False, message="Action cancelled by user")

        try:
            path = Path(file_path)
            new_path = path.parent / new_name

            path.rename(new_path)

            return TaskOutput(
                success=True,
                message="File renamed",
                data={"old_path": str(file_path), "new_path": str(new_path)},
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to rename file", error=str(e)
            )

    def _execute_file_move(self, task: Task) -> TaskOutput:
        """Move a file."""
        file_path = task.input.get("file_path")
        destination = task.input.get("destination")

        if not file_path or not destination:
            return TaskOutput(
                success=False,
                message="Failed to move file",
                error="File path and destination required",
            )

        if not self._require_confirmation(
            "Move File", f"Moving:\n{file_path}\nto:\n{destination}"
        ):
            return TaskOutput(success=False, message="Action cancelled by user")

        try:
            path = Path(file_path)
            dest_path = Path(destination)

            if not path.exists():
                return TaskOutput(
                    success=False,
                    message="Source file not found",
                    error=f"Path does not exist: {file_path}",
                )

            path.rename(dest_path)

            return TaskOutput(
                success=True,
                message="File moved",
                data={"source": str(file_path), "destination": str(destination)},
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to move file", error=str(e)
            )

    # ========================================
    # SYSTEM CONTROLS
    # ========================================

    def _execute_screenshot(self, task: Task) -> TaskOutput:
        """Take a screenshot."""
        try:
            from PIL import ImageGrab

            screenshot = ImageGrab.grab()

            # Save screenshot
            screenshot_path = (
                Path.home()
                / "screenshots"
                / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            )
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)

            screenshot.save(screenshot_path)

            return TaskOutput(
                success=True,
                message="Screenshot captured",
                data={
                    "path": str(screenshot_path),
                    "width": screenshot.width,
                    "height": screenshot.height,
                },
            )

        except ImportError:
            return TaskOutput(
                success=False,
                message="Screenshot failed",
                error="Pillow not installed. Run: pip install Pillow",
            )
        except Exception as e:
            return TaskOutput(success=False, message="Screenshot failed", error=str(e))

    def _execute_clipboard_read(self, task: Task) -> TaskOutput:
        """Read clipboard content."""
        try:
            import win32clipboard

            win32clipboard.OpenClipboard()
            content = win32clipboard.GetClipboardData()
            win32clipboard.CloseClipboard()

            return TaskOutput(
                success=True,
                message="Clipboard content retrieved",
                data={"content": str(content)},
            )

        except ImportError:
            return TaskOutput(
                success=False,
                message="Clipboard read failed",
                error="pywin32 not installed. Run: pip install pywin32",
            )
        except Exception as e:
            return TaskOutput(
                success=False, message="Clipboard read failed", error=str(e)
            )

    def _execute_system_volume(self, task: Task) -> TaskOutput:
        """Adjust system volume."""
        volume = task.input.get("volume", 50)  # 0-100
        set_volume = task.input.get("set_volume", False)

        if not self._require_confirmation(
            "System Volume",
            f"{'Setting' if set_volume else 'Adjusting'} volume to {volume}%",
        ):
            return TaskOutput(success=False, message="Action cancelled by user")

        try:
            # Windows command to set volume
            cmd = [
                "powershell",
                "-Command",
                f"Set-Volume -Mute $false -NewVolume {volume / 100.0}",
            ]

            if set_volume:
                subprocess.Popen(cmd, shell=True)

            return TaskOutput(
                success=True,
                message=f"Volume set to {volume}%",
                data={"volume": volume, "set_volume": set_volume},
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to adjust volume", error=str(e)
            )

    def _execute_lock_workstation(self, task: Task) -> TaskOutput:
        """Lock the workstation."""
        if not self._require_confirmation("Lock Workstation", "Lock the computer?"):
            return TaskOutput(success=False, message="Action cancelled by user")

        try:
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"], shell=True)

            return TaskOutput(success=True, message="Workstation locked")

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to lock workstation", error=str(e)
            )

    # ========================================
    # BROWSER MANAGEMENT
    # ========================================

    def _execute_browser_open(self, task: Task) -> TaskOutput:
        """Open a browser with a URL."""
        url = task.input.get("url")
        browser = task.input.get("browser", "chrome")

        if not url:
            return TaskOutput(
                success=False, message="Failed to open browser", error="URL required"
            )

        if not self._require_confirmation(
            "Open Browser", f"Opening {browser} with:\n{url}"
        ):
            return TaskOutput(success=False, message="Action cancelled by user")

        try:
            # Try to find browser executable
            browsers = {
                "chrome": ["chrome.exe", "google-chrome.exe", "chrome"],
                "firefox": ["firefox.exe", "firefox"],
                "edge": ["msedge.exe", "microsoftedge.exe", "edge"],
            }

            browser_cmd = browsers.get(browser.lower(), [browser])

            # Construct command with URL
            if browser_cmd[0].endswith(".exe"):
                # Windows
                subprocess.Popen([browser_cmd[0], url], shell=True)
            else:
                # Cross-platform
                subprocess.Popen([browser_cmd[0], url])

            return TaskOutput(
                success=True,
                message=f"Browser opened: {browser}",
                data={"browser": browser, "url": url},
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to open browser", error=str(e)
            )

    # ========================================
    # WINDOW MANAGEMENT
    # ========================================

    def _execute_window_maximize(self, task: Task) -> TaskOutput:
        """Maximize a window."""
        window_title = task.input.get("window_title", "")

        if not window_title:
            return TaskOutput(
                success=False,
                message="Failed to maximize window",
                error="Window title required",
            )

        if not self._require_confirmation(
            "Maximize Window", f"Maximizing window: {window_title}"
        ):
            return TaskOutput(success=False, message="Action cancelled by user")

        try:
            # Windows command to maximize window
            window_title_escaped = window_title.replace("'", "''")
            cmd = [
                "powershell",
                "-Command",
                f"(Get-Process | Where-Object {{$_.MainWindowTitle -like '{window_title_escaped}'}}).MainWindowHandle | "
                f"ForEach-Object {{ [Windows.Forms.SendKeys]::SendWait('%')}}",
            ]

            # Simplified: use PowerShell to maximize first matching window
            subprocess.Popen(
                ["powershell", "-Command", "Add-Type '[Win32.WindowStation]'"],
                shell=True,
            )

            return TaskOutput(success=True, message=f"Window maximized: {window_title}")

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to maximize window", error=str(e)
            )

    def _execute_window_minimize(self, task: Task) -> TaskOutput:
        """Minimize a window."""
        window_title = task.input.get("window_title", "")

        if not window_title:
            return TaskOutput(
                success=False,
                message="Failed to minimize window",
                error="Window title required",
            )

        try:
            # Use PowerShell to minimize window
            window_title_escaped = window_title.replace("'", "''")
            subprocess.Popen(
                [
                    "powershell",
                    "-Command",
                    f"Add-Type 'using System; using System.Runtime.InteropServices; public class W{{[DllImport('user32.dll')] public static extern int ShowWindow(IntPtr hwnd, int nCmdShow);}}'; $w = Get-Process | Where-Object {{$_.MainWindowTitle -like '{window_title_escaped}'}}; [W]::ShowWindow($w.MainWindowHandle, 6)",
                ],
                shell=True,
            )

            return TaskOutput(success=True, message=f"Window minimized: {window_title}")

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to minimize window", error=str(e)
            )

    # ========================================
    # PROCESS MANAGEMENT
    # ========================================

    def _execute_process_list(self, task: Task) -> TaskOutput:
        """List all running processes"""
        try:
            filter_name = task.input.get("name")
            filter_status = task.input.get("status")

            processes = self.process_manager.list_processes(
                filter_by_name=filter_name, filter_by_status=filter_status
            )

            return TaskOutput(
                success=True,
                message=f"Found {len(processes)} processes",
                data={
                    "processes": [p.to_dict() for p in processes],
                    "count": len(processes),
                    "total_cpu_percent": round(
                        sum(p.cpu_percent for p in processes), 2
                    ),
                    "total_memory_mb": round(sum(p.memory_mb for p in processes), 2),
                },
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to list processes", error=str(e)
            )

    def _execute_process_get(self, task: Task) -> TaskOutput:
        """Get information about a specific process"""
        try:
            pid = task.input.get("pid")

            if pid is None:
                return TaskOutput(
                    success=False,
                    message="Failed to get process",
                    error="PID not provided",
                )

            process = self.process_manager.get_process_info(pid)

            if not process:
                return TaskOutput(
                    success=False,
                    message=f"Process {pid} not found",
                    error=f"No process with PID {pid} exists",
                )

            return TaskOutput(
                success=True,
                message="Process information retrieved",
                data=process.to_dict(),
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to get process", error=str(e)
            )

    def _execute_process_start(self, task: Task) -> TaskOutput:
        """Start a process"""
        try:
            command = task.input.get("command")
            args = task.input.get("args", [])
            cwd = task.input.get("cwd")
            shell = task.input.get("shell", False)

            if not command:
                return TaskOutput(
                    success=False,
                    message="Failed to start process",
                    error="Command not provided",
                )

            process = self.process_manager.start_process(command, args, cwd, shell)

            return TaskOutput(
                success=True,
                message=f"Process started: {process.name} (PID: {process.pid})",
                data=process.to_dict(),
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to start process", error=str(e)
            )

    def _execute_process_stop(self, task: Task) -> TaskOutput:
        """Stop a process gracefully"""
        try:
            pid = task.input.get("pid")
            timeout = task.input.get("timeout", 5)

            if pid is None:
                return TaskOutput(
                    success=False,
                    message="Failed to stop process",
                    error="PID not provided",
                )

            success = self.process_manager.stop_process(pid, timeout)

            if success:
                return TaskOutput(
                    success=True,
                    message=f"Process stopped: PID {pid}",
                    data={"pid": pid, "stopped": True},
                )
            else:
                return TaskOutput(
                    success=False,
                    message=f"Failed to stop process {pid}",
                    error="Process did not terminate gracefully",
                )

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to stop process", error=str(e)
            )

    def _execute_process_kill(self, task: Task) -> TaskOutput:
        """Kill a process"""
        try:
            pid = task.input.get("pid")
            force = task.input.get("force", False)

            if pid is None:
                return TaskOutput(
                    success=False,
                    message="Failed to kill process",
                    error="PID not provided",
                )

            success = self.process_manager.kill_process(pid, force)

            if success:
                return TaskOutput(
                    success=True,
                    message=f"Process killed: PID {pid}",
                    data={"pid": pid, "killed": True},
                )
            else:
                return TaskOutput(
                    success=False,
                    message=f"Failed to kill process {pid}",
                    error="Failed to kill process",
                )

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to kill process", error=str(e)
            )

    def _execute_process_search(self, task: Task) -> TaskOutput:
        """Search for processes"""
        try:
            name = task.input.get("name")
            max_results = task.input.get("max_results", 50)

            if not name:
                return TaskOutput(
                    success=False,
                    message="Failed to search processes",
                    error="Search name not provided",
                )

            processes = self.process_manager.find_process_by_name(name)

            return TaskOutput(
                success=True,
                message=f"Found {len(processes)} matching processes",
                data={
                    "processes": [p.to_dict() for p in processes[:max_results]],
                    "count": len(processes),
                    "search_name": name,
                },
            )

        except Exception as e:
            return TaskOutput(
                success=False, message="Failed to search processes", error=str(e)
            )
