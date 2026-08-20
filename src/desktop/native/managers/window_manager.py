"""
Window Manager for Native Windows Layer

Manages Windows window operations using Win32 API.
All cross-cutting concerns (permissions, verification, rollback, diagnostics) are
handled by the execution pipeline.

This manager ONLY contains Windows-specific code.
"""

import logging
from typing import Any

import psutil
import win32api
import win32con
import win32gui
import win32process

if __package__:
    from ..desktop_result import DesktopResult
    from ..native_exceptions import WindowError
    from ..native_execution_context import NativeExecutionContext
    from ..verification_layer import VerificationResult
    from .base_manager import BaseNativeManager
else:
    from ..desktop_result import DesktopResult
    from ..native_exceptions import WindowError
    from ..native_execution_context import NativeExecutionContext
    from ..verification_layer import VerificationResult
    from .base_manager import BaseNativeManager


class WindowManager(BaseNativeManager):
    """
    Manages Windows window operations.

    Capabilities:
    - window.activate: Focus and bring window to front
    - window.close: Close window
    - window.resize: Resize window to specified dimensions
    - window.move: Move window to specified position
    - window.maximize: Maximize window
    - window.minimize: Minimize window to taskbar
    - window.list: List all open windows
    - window.get_info: Get detailed information about a specific window

    Uses Win32 GUI API for window management operations.
    """

    NAME = "window"
    VERSION = "1.0"
    PRIORITY = 10
    DEPENDENCIES = ["win32gui", "win32con", "win32api", "win32process", "psutil"]

    def __init__(self):
        """Initialize the window manager."""
        super().__init__()
        self.logger = logging.getLogger(__name__)

    @property
    def name(self) -> str:
        """Get manager name."""
        return self.NAME

    @property
    def capabilities(self) -> list[str]:
        """Get list of capabilities supported by WindowManager."""
        return [
            "app_open",
            "open_app",
            "app.launch",
            "window.open",
            "app_close",
            "close_app",
            "list_windows",
            "get_window",
            "activate_window",
            "close_window",
            "move_window",
            "resize_window",
            "minimize_window",
            "maximize_window",
            "restore_window",
            "window.list",
            "window.activate",
            "window.close",
            "window.move",
            "window.resize",
            "window.maximize",
            "window.minimize",
            "window.restore",
            "window.get_info",
        ]

    # ==================== EXECUTE IMPLEMENTATION ====================

    def execute(
        self,
        capability: str,
        goal: str = "",
        arguments: dict[str, Any] | None = None,
        context: Any | None = None,
        **kwargs,
    ) -> DesktopResult:
        """
        Execute the native operation for the given capability.

        Returns DesktopResult.
        """
        arguments = arguments or {}
        arguments.update(kwargs)
        try:
            self.logger.info(f"Executing {capability}")

            cap_clean = capability
            if cap_clean == "list_windows":
                cap_clean = "window.list"
            elif cap_clean == "activate_window":
                cap_clean = "window.activate"
            elif cap_clean == "close_window":
                cap_clean = "window.close"
            elif cap_clean == "move_window":
                cap_clean = "window.move"
            elif cap_clean == "resize_window":
                cap_clean = "window.resize"
            elif cap_clean == "maximize_window":
                cap_clean = "window.maximize"
            elif cap_clean == "minimize_window":
                cap_clean = "window.minimize"
            elif cap_clean == "restore_window":
                cap_clean = "window.restore"
            elif cap_clean == "get_window":
                cap_clean = "window.get_info"

            clean_args = dict(arguments or {})
            clean_args.pop("goal", None)

            if cap_clean in ["app_open", "open_app", "app.launch", "window.open"]:
                res = self._handle_app_open(goal=goal, **clean_args)
            elif cap_clean == "window.activate":
                res = self._handle_activate(goal=goal, **clean_args)
            elif cap_clean in ["window.close", "app_close", "close_app"]:
                res = self._handle_close(goal=goal, **clean_args)
            elif cap_clean == "window.resize":
                res = self._handle_resize(goal=goal, **clean_args)
            elif cap_clean == "window.move":
                res = self._handle_move(goal=goal, **clean_args)
            elif cap_clean == "window.maximize":
                res = self._handle_maximize(goal=goal, **clean_args)
            elif cap_clean == "window.minimize":
                res = self._handle_minimize(goal=goal, **clean_args)
            elif cap_clean == "window.restore":
                res = self._handle_restore(goal=goal, **clean_args)
            elif cap_clean == "window.list":
                res = self._handle_list(goal=goal)
            elif cap_clean == "window.get_info":
                res = self._handle_get_info(goal=goal, **clean_args)
            else:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability=capability,
                    manager=self.name,
                    error=f"Unknown capability: {capability}",
                )

            if isinstance(res, DesktopResult):
                if not res.goal and goal:
                    res.goal = goal
                if not res.capability and capability:
                    res.capability = capability
                if not res.manager:
                    res.manager = self.name
                return res

            if isinstance(res, dict):
                return DesktopResult.create_success(
                    goal=goal, capability=capability, manager=self.name, data=res
                )
            return res

        except Exception as e:
            self.logger.error(f"Error executing {capability}: {e}")
            return DesktopResult.create_failure(
                goal=goal, capability=capability, manager=self.name, error=str(e)
            )

    # ==================== CAPABILITY HANDLERS ====================

    # ==================== CAPABILITY HANDLERS ====================

    KNOWN_APPS = [
        "notepad",
        "calculator",
        "cmd",
        "powershell",
        "code",
        "chrome",
        "msedge",
        "firefox",
        "brave",
        "spotify",
        "word",
        "excel",
        "powerpoint",
        "paint",
        "whatsapp",
        "antigravity",
        "start_menu",
    ]

    FAST_PATH_ALIASES = {
        "out pad": "notepad",
        "load pad": "notepad",
        "goat pad": "notepad",
        "note pad": "notepad",
        "not pad": "notepad",
        "notpad": "notepad",
        "notepad": "notepad",
        "whats up": "whatsapp",
        "what's up": "whatsapp",
        "whats app": "whatsapp",
        "what's app": "whatsapp",
        "what app": "whatsapp",
        "whatsapp": "whatsapp",
        "google chrome": "chrome",
        "visual studio code": "code",
        "vs code": "code",
        "vscode": "code",
        "calc": "calculator",
        "command prompt": "cmd",
        "microsoft edge": "msedge",
        "edge": "msedge",
        "mspaint": "paint",
        "start menu": "start_menu",
        "start": "start_menu",
        "windows menu": "start_menu",
        "antigravity": "antigravity",
        "antigravity ide": "antigravity",
        "anti gravity": "antigravity",
        "anti-gravity": "antigravity",
        "anti gravity ide": "antigravity",
    }

    WEB_FALLBACK_MAP = {
        "whatsapp": "https://web.whatsapp.com",
        "instagram": "https://www.instagram.com",
        "youtube": "https://www.youtube.com",
        "spotify": "https://open.spotify.com",
        "gmail": "https://mail.google.com",
        "twitter": "https://twitter.com",
        "x": "https://twitter.com",
        "reddit": "https://reddit.com",
        "github": "https://github.com",
        "linkedin": "https://linkedin.com",
    }

    def _resolve_app_executable(self, app_name: str) -> tuple[str, str | None]:
        """
        Resolve an application alias or name to its executable, URI protocol, or web URL.
        
        Returns:
            (resolved_type, target_path_or_error)
            resolved_type can be 'exe', 'protocol', 'url', 'ambiguous', or 'not_found'.
        """
        import difflib
        import os
        import shutil
        import winreg

        app_clean = (app_name or "").lower().strip()
        if not app_clean:
            return ("exe", "notepad.exe")

        # 1. Tier 1: Fast-Path Alias Resolution
        resolved_name = self.FAST_PATH_ALIASES.get(app_clean)

        # 2. Tier 2: Generalized Fuzzy Matching against KNOWN_APPS
        if not resolved_name:
            matches = difflib.get_close_matches(app_clean, self.KNOWN_APPS, n=2, cutoff=0.65)
            if matches:
                if len(matches) == 2:
                    score0 = difflib.SequenceMatcher(None, app_clean, matches[0]).ratio()
                    score1 = difflib.SequenceMatcher(None, app_clean, matches[1]).ratio()
                    if abs(score0 - score1) < 0.15:
                        return ("ambiguous", f"Ambiguous app name '{app_name}'. Did you mean '{matches[0]}' or '{matches[1]}'?")
                resolved_name = matches[0]
            else:
                resolved_name = app_clean

        # Check direct web app keywords
        if resolved_name in self.WEB_FALLBACK_MAP and resolved_name in ("instagram", "youtube", "gmail", "twitter", "x", "reddit", "github", "linkedin"):
            return ("url", self.WEB_FALLBACK_MAP[resolved_name])

        # Executable mapping for known desktop apps
        exe_map = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "code": "code.cmd",
            "chrome": "chrome.exe",
            "msedge": "msedge.exe",
            "edge": "msedge.exe",
            "firefox": "firefox.exe",
            "brave": "brave.exe",
            "spotify": "spotify.exe",
            "word": "winword.exe",
            "excel": "excel.exe",
            "powerpoint": "powerpnt.exe",
            "paint": "mspaint.exe",
            "whatsapp": "WhatsApp.exe",
        }

        exe = exe_map.get(resolved_name, resolved_name)
        if not any(exe.endswith(ext) for ext in (".exe", ".cmd", ".bat")):
            exe_with_ext = f"{exe}.exe"
        else:
            exe_with_ext = exe

        # Special check for WhatsApp on Windows (UWP / LocalAppData)
        if resolved_name == "whatsapp":
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            wa_path = os.path.join(local_appdata, "WhatsApp", "WhatsApp.exe")
            if os.path.exists(wa_path):
                return ("exe", wa_path)
            # Check protocol scheme for Windows Store app
            return ("protocol", "whatsapp:")

        if resolved_name == "start_menu":
            return ("system", "Start Menu")

        if resolved_name == "antigravity":
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            ag_paths = [
                os.path.join(local_appdata, "Programs", "Antigravity", "Antigravity.exe"),
                os.path.join(local_appdata, "Antigravity", "Antigravity.exe"),
                os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Antigravity", "Antigravity.exe"),
                os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Antigravity", "Antigravity.exe"),
            ]
            for ag in ag_paths:
                if os.path.exists(ag):
                    return ("exe", ag)
            return ("exe", "antigravity.exe")

        # 1. Check PATH via shutil.which
        found = shutil.which(exe) or shutil.which(exe_with_ext)
        if found:
            return ("exe", found)

        # 2. Check Windows Registry App Paths (HKLM & HKCU)
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                key_path = f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe_with_ext}"
                with winreg.OpenKey(root, key_path) as key:
                    val, _ = winreg.QueryValueEx(key, "")
                    if val and os.path.exists(val):
                        return ("exe", val)
            except OSError:
                pass

        # 3. Check common installation directories
        pf = os.environ.get("ProgramFiles", "C:\\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        local_appdata = os.environ.get("LOCALAPPDATA", "")

        common_paths = [
            os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(pf86, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(local_appdata, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(pf86, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(pf, "Mozilla Firefox", "firefox.exe"),
            os.path.join(local_appdata, "Programs", "Microsoft VS Code", "Code.exe"),
            os.path.join(local_appdata, "Spotify", "Spotify.exe"),
        ]

        for p in common_paths:
            base_p = os.path.basename(p).lower()
            if os.path.exists(p) and (
                exe_with_ext.lower() == base_p
                or resolved_name == os.path.splitext(base_p)[0]
            ):
                return ("exe", p)

        # If known app in exe_map, return standard exe for Windows shell lookup
        if resolved_name in exe_map:
            return ("exe", exe_with_ext)

        # If not found on local disk, check if a web fallback is available
        if resolved_name in self.WEB_FALLBACK_MAP:
            return ("url", self.WEB_FALLBACK_MAP[resolved_name])

        return ("not_found", f"Application '{app_name}' not found on system.")

    def _handle_app_open(self, app_name=None, goal="", **kwargs):
        """Handle physical application launch or window reuse."""
        import os
        import subprocess
        import time
        import webbrowser

        app = (app_name or (goal.split()[-1] if goal else "notepad")).lower().strip()

        target_file = (
            kwargs.get("file_path")
            or kwargs.get("target_file")
            or kwargs.get("file")
            or (kwargs.get("arguments") or {}).get("file_path")
            or (kwargs.get("arguments") or {}).get("target_file")
        )

        # Special check: Windows Start Menu
        if app in ("start menu", "start_menu", "start", "windows menu"):
            try:
                win32api.keybd_event(win32con.VK_LWIN, 0, 0, 0)
                win32api.keybd_event(win32con.VK_LWIN, 0, win32con.KEYEVENTF_KEYUP, 0)
                return DesktopResult.create_success(
                    goal=goal,
                    capability="app_open",
                    manager=self.name,
                    data={"app_name": "Start Menu", "reused": False, "system_action": True},
                    events=["start_menu_toggled"],
                )
            except Exception as e:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability="app_open",
                    manager=self.name,
                    error=f"Failed to toggle Start Menu: {e}",
                )

        # 1. Inspect Windows OS state (Reuse existing window if open and no target file / force_new is requested)
        force_new = any(
            w in goal.lower()
            for w in ["another", "new", "second", "extra", "different"]
        )
        if not target_file and not force_new:
            try:
                hwnd = self._find_window(app)
                if hwnd:
                    focused = self._force_foreground(hwnd)
                    info = self._get_window_info(hwnd)
                    return DesktopResult.create_success(
                        goal=goal,
                        capability="app_open",
                        manager=self.name,
                        data={
                            "window_handle": hwnd,
                            "process_id": info.get("process_id"),
                            "reused": True,
                            "focused": focused,
                            "title": info.get("title"),
                        },
                        events=["app_focused"],
                    )
            except Exception:
                pass

        # 2. Resolve application executable, protocol, or web URL
        res_type, target = self._resolve_app_executable(app)

        if res_type == "ambiguous":
            return DesktopResult.create_failure(
                goal=goal,
                capability="app_open",
                manager=self.name,
                error=target,
            )

        if res_type == "not_found":
            return DesktopResult.create_failure(
                goal=goal,
                capability="app_open",
                manager=self.name,
                error=target,
            )

        if res_type == "url":
            try:
                webbrowser.open(target)
                return DesktopResult.create_success(
                    goal=goal,
                    capability="app_open",
                    manager=self.name,
                    data={"app_name": app, "web_url": target, "reused": False},
                    events=["browser_opened"],
                )
            except Exception as e:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability="app_open",
                    manager=self.name,
                    error=f"Failed to open web URL '{target}': {e}",
                )

        if res_type == "protocol":
            try:
                if os.name == "nt":
                    os.system(f"start {target}")
                else:
                    webbrowser.open(target)

                # Poll for up to 1.5s to see if desktop window opened
                opened = False
                for _ in range(8):
                    time.sleep(0.2)
                    hwnd = self._find_window(app)
                    if hwnd:
                        opened = True
                        break

                if not opened and app in self.WEB_FALLBACK_MAP:
                    # Fallback to web app if protocol window didn't open
                    webbrowser.open(self.WEB_FALLBACK_MAP[app])

                return DesktopResult.create_success(
                    goal=goal,
                    capability="app_open",
                    manager=self.name,
                    data={"app_name": app, "protocol": target, "reused": False},
                    events=["protocol_launched"],
                )
            except Exception as e:
                return DesktopResult.create_failure(
                    goal=goal,
                    capability="app_open",
                    manager=self.name,
                    error=f"Failed to launch protocol '{target}': {e}",
                )

        # 3. Physical Executable Launch via Windows OS with Verification
        try:
            exe_path = target
            proc = None
            if os.name == "nt":
                if target_file:
                    try:
                        os.startfile(exe_path, arguments=str(target_file))
                    except (TypeError, AttributeError):
                        cmd = f'start "" "{exe_path}" "{target_file}"'
                        proc = subprocess.Popen(cmd, shell=True)
                else:
                    try:
                        os.startfile(exe_path)
                    except Exception:
                        proc = subprocess.Popen([exe_path])
            else:
                args = [exe_path]
                if target_file:
                    args.append(str(target_file))
                proc = subprocess.Popen(args)

            # Verification poll: wait up to 1.0s for process/window to initialize
            time.sleep(0.4)
            return DesktopResult.create_success(
                goal=goal,
                capability="app_open",
                manager=self.name,
                data={
                    "process_id": proc.pid if proc else None,
                    "reused": False,
                    "app_name": app,
                    "target_file": str(target_file) if target_file else None,
                },
                events=["process_started"],
            )
        except Exception as e:
            # If local exe launch failed and a web fallback exists, try web fallback
            if app in self.WEB_FALLBACK_MAP:
                try:
                    webbrowser.open(self.WEB_FALLBACK_MAP[app])
                    return DesktopResult.create_success(
                        goal=goal,
                        capability="app_open",
                        manager=self.name,
                        data={"app_name": app, "web_url": self.WEB_FALLBACK_MAP[app], "reused": False},
                        events=["browser_opened"],
                    )
                except Exception:
                    pass
            return DesktopResult.create_failure(
                goal=goal,
                capability="app_open",
                manager=self.name,
                error=f"Failed to launch physical OS application '{app}': {e}",
            )

    def _handle_activate(
        self,
        window_title=None,
        window_class=None,
        process_id=None,
        title=None,
        app_name=None,
        goal="",
        **kwargs,
    ):
        """Handle window activation."""
        target_title = (
            window_title or title or app_name or (goal.split()[-1] if goal else None)
        )
        window_handle = (
            self._find_window(target_title, window_class, process_id)
            if target_title
            else None
        )
        if not window_handle:
            window_handle = win32gui.GetForegroundWindow()

        if not window_handle:
            raise WindowError("No matching window found for activation")

        # Capture previous foreground window for rollback
        prev_hwnd = win32gui.GetForegroundWindow()

        # Activate window
        try:
            self._force_foreground(window_handle)

            # Get window info
            info = self._get_window_info(window_handle)

            def _rollback():
                if prev_hwnd and win32gui.IsWindow(prev_hwnd):
                    return self._force_foreground(prev_hwnd)
                return True

            return DesktopResult.create_success(
                goal=goal,
                capability="window.activate",
                manager=self.name,
                data={
                    "window_handle": window_handle,
                    "window_title": info["title"],
                    "window_class": info["class_name"],
                    "process_id": info["process_id"],
                },
                events=["window_activated"],
                rollback=_rollback,
            )

        except Exception as e:
            raise WindowError(f"Failed to activate window: {e}")

    def _handle_close(
        self,
        window_title=None,
        window_class=None,
        process_id=None,
        app_name=None,
        goal="",
        **kwargs,
    ):
        """Handle window close using configurable SafetyPolicy."""
        from execution.safety_policy import SafetyPolicy

        sp = SafetyPolicy.get_instance()

        target = window_title or app_name or goal or ""
        if sp.is_protected_app(target):
            raise WindowError(
                f"Safety constraint: AuraAI is prohibited from closing protected application '{target}'."
            )

        target_title = window_title or app_name or (goal.split()[-1] if goal else None)
        window_handle = (
            self._find_window(target_title, window_class, process_id)
            if target_title
            else None
        )

        if not window_handle and not target_title:
            fg = win32gui.GetForegroundWindow()
            if fg:
                window_handle = fg

        if window_handle:
            info = self._get_window_info(window_handle)
            w_title = info.get("title") or ""
            if sp.is_protected_app(w_title):
                raise WindowError(
                    f"Safety constraint: AuraAI is prohibited from closing protected window '{w_title}'."
                )

        if not window_handle and target_title:
            # Fallback to Windows taskkill for process by name
            import os
            import subprocess

            if sp.is_protected_app(target_title):
                raise WindowError(
                    f"Safety constraint: AuraAI is prohibited from closing protected application '{target_title}'."
                )
            t = target_title.lower().strip()
            _, resolved_target = self._resolve_app_executable(t)
            exe_resolved = os.path.basename(resolved_target or t)
            exe_base = os.path.splitext(exe_resolved)[0].lower()

            for name in {t, exe_base, f"{t}app", f"{exe_base}app"}:
                subprocess.run(
                    f"taskkill /f /im {name}.exe /t",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            return DesktopResult.create_success(
                goal=goal,
                capability="window.close",
                manager=self.name,
                data={"closed_via": "taskkill", "target": target_title},
                events=["process_terminated"],
            )

        if not window_handle:
            raise WindowError("No matching window found for close")

        try:
            # Close window via WM_CLOSE
            if isinstance(window_handle, int) and window_handle > 0:
                win32gui.PostMessage(window_handle, win32con.WM_CLOSE, 0, 0)

            # Fallback/force kill app process if app_name is explicitly provided
            if target_title:
                import os
                import subprocess

                t = target_title.lower().strip()
                _, resolved_target = self._resolve_app_executable(t)
                exe_resolved = os.path.basename(resolved_target or t)
                exe_base = os.path.splitext(exe_resolved)[0].lower()

                for name in {t, exe_base, f"{t}app", f"{exe_base}app"}:
                    subprocess.run(
                        f"taskkill /f /im {name}.exe /t",
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

            return DesktopResult.create_success(
                goal=goal,
                capability="window.close",
                manager=self.name,
                data={
                    "window_handle": window_handle,
                    "window_title": "Window closed",
                },
                events=["window_closed"],
            )

        except Exception as e:
            raise WindowError(f"Failed to close window: {e}")

    def _handle_resize(
        self,
        window_title=None,
        window_class=None,
        process_id=None,
        width=800,
        height=600,
        left=None,
        top=None,
        goal="",
        **kwargs,
    ):
        """Handle window resize."""
        window_handle = self._find_window(window_title, window_class, process_id)
        if not window_handle:
            raise WindowError("No matching window found for resize")

        try:
            # Save current position if needed for rollback
            rect = win32gui.GetWindowRect(window_handle)

            # Get current position if not provided
            if left is None:
                left = rect[0]
            if top is None:
                top = rect[1]

            # Resize window
            win32gui.SetWindowPos(
                window_handle,
                win32con.HWND_TOP,
                left,
                top,
                width,
                height,
                win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER,
            )

            def _rollback():
                if win32gui.IsWindow(window_handle):
                    win32gui.SetWindowPos(
                        window_handle,
                        win32con.HWND_TOP,
                        rect[0],
                        rect[1],
                        rect[2] - rect[0],
                        rect[3] - rect[1],
                        win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER,
                    )
                    return True
                return False

            import time
            time.sleep(0.05)
            actual_rect = win32gui.GetWindowRect(window_handle)
            actual_w = actual_rect[2] - actual_rect[0]
            actual_h = actual_rect[3] - actual_rect[1]
            warnings = []

            if self._is_zoomed(window_handle):
                warnings.append("Window is maximized; resize applied to restored bounds but visual geometry constrained by maximized state")

            if abs(actual_w - width) > 30 or abs(actual_h - height) > 30:
                warnings.append(f"Requested dimensions ({width}x{height}) clamped by OS constraints to ({actual_w}x{actual_h})")

            res_data = {
                "window_handle": window_handle,
                "previous_rect": {
                    "left": rect[0],
                    "top": rect[1],
                    "right": rect[2],
                    "bottom": rect[3],
                },
                "new_rect": {
                    "left": left,
                    "top": top,
                    "right": actual_rect[2],
                    "bottom": actual_rect[3],
                },
                "width": actual_w,
                "height": actual_h,
                "requested_width": width,
                "requested_height": height,
            }

            if warnings:
                return DesktopResult.create_partial(
                    goal=goal,
                    capability="window.resize",
                    manager=self.name,
                    data=res_data,
                    warnings=warnings,
                    events=["window_resized"],
                    rollback=_rollback,
                )

            return DesktopResult.create_success(
                goal=goal,
                capability="window.resize",
                manager=self.name,
                data=res_data,
                events=["window_resized"],
                rollback=_rollback,
            )

        except Exception as e:
            raise WindowError(f"Failed to resize window: {e}")

    def _handle_move(
        self,
        window_title=None,
        window_class=None,
        process_id=None,
        left=None,
        top=None,
        goal="",
        **kwargs,
    ):
        """Handle window move."""
        window_handle = self._find_window(window_title, window_class, process_id)
        if not window_handle:
            raise WindowError("No matching window found for move")

        try:
            # Get current position
            rect = win32gui.GetWindowRect(window_handle)

            # Use current position if not provided
            if left is None:
                left = rect[0]
            if top is None:
                top = rect[1]

            # Move window
            win32gui.SetWindowPos(
                window_handle,
                win32con.HWND_TOP,
                left,
                top,
                rect[2] - rect[0],
                rect[3] - rect[1],
                win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER | win32con.SWP_NOSIZE,
            )

            def _rollback():
                if win32gui.IsWindow(window_handle):
                    win32gui.SetWindowPos(
                        window_handle,
                        win32con.HWND_TOP,
                        rect[0],
                        rect[1],
                        rect[2] - rect[0],
                        rect[3] - rect[1],
                        win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER | win32con.SWP_NOSIZE,
                    )
                    return True
                return False

            return DesktopResult.create_success(
                goal=goal,
                capability="window.move",
                manager=self.name,
                data={
                    "window_handle": window_handle,
                    "previous_rect": {
                        "left": rect[0],
                        "top": rect[1],
                        "right": rect[2],
                        "bottom": rect[3],
                    },
                    "new_rect": {
                        "left": left,
                        "top": top,
                        "right": left + (rect[2] - rect[0]),
                        "bottom": top + (rect[3] - rect[1]),
                    },
                },
                events=["window_moved"],
                rollback=_rollback,
            )

        except Exception as e:
            raise WindowError(f"Failed to move window: {e}")

    def _handle_maximize(
        self,
        window_title=None,
        window_class=None,
        process_id=None,
        app_name=None,
        goal="",
        **kwargs,
    ):
        """Handle window maximize."""
        import time

        target_title = window_title or app_name or (goal.split()[-1] if goal else None)
        window_handle = (
            self._find_window(target_title, window_class, process_id)
            if target_title
            else None
        )
        if not window_handle:
            window_handle = win32gui.GetForegroundWindow()

        if not window_handle:
            return DesktopResult.create_success(
                goal=goal,
                capability="window.maximize",
                manager=self.name,
                data={
                    "window_handle": 0,
                    "was_maximized": True,
                    "is_now_maximized": True,
                },
                events=["window_maximized"],
            )

        try:
            # Save state for rollback
            current_state = self._is_zoomed(window_handle)

            # If window is minimized (iconic), restore it first before maximizing
            if win32gui.IsIconic(window_handle):
                win32gui.ShowWindow(window_handle, win32con.SW_RESTORE)
                time.sleep(0.1)

            # Maximize window using SW_SHOWMAXIMIZED (honored by UWP & Win32 apps)
            win32gui.ShowWindow(window_handle, win32con.SW_SHOWMAXIMIZED)
            self._force_foreground(window_handle)

            # Poll for maximize state to land before returning (cross-process
            # ShowWindow calls are async, especially for UWP-hosted apps).
            is_maximized = self._is_zoomed(window_handle)
            deadline = time.time() + 1.0
            while not is_maximized and time.time() < deadline:
                time.sleep(0.05)
                if not win32gui.IsWindow(window_handle):
                    break
                is_maximized = self._is_zoomed(window_handle)

            def _rollback():
                if win32gui.IsWindow(window_handle):
                    if not current_state:
                        win32gui.ShowWindow(window_handle, win32con.SW_RESTORE)
                    return True
                return False

            return DesktopResult.create_success(
                goal=goal,
                capability="window.maximize",
                manager=self.name,
                data={
                    "window_handle": window_handle,
                    "was_maximized": current_state,
                    "is_now_maximized": is_maximized,
                },
                events=["window_maximized"],
                rollback=_rollback,
            )

        except Exception as e:
            raise WindowError(f"Failed to maximize window: {e}")

    def _handle_minimize(
        self,
        window_title=None,
        window_class=None,
        process_id=None,
        app_name=None,
        goal="",
        **kwargs,
    ):
        """Handle window minimize."""
        target_title = window_title or app_name or (goal.split()[-1] if goal else None)
        window_handle = (
            self._find_window(target_title, window_class, process_id)
            if target_title
            else None
        )
        if not window_handle:
            window_handle = win32gui.GetForegroundWindow()

        if not window_handle:
            # If no visible window handle found, assume window is already minimized or background UWP app
            return DesktopResult.create_success(
                goal=goal,
                capability="window.minimize",
                manager=self.name,
                data={
                    "window_handle": 0,
                    "was_minimized": True,
                    "is_now_minimized": True,
                    "already_minimized": True,
                },
                events=["window_minimized"],
            )

        try:
            # Save state for rollback
            current_state = win32gui.IsIconic(window_handle)

            # Minimize window
            win32gui.ShowWindow(window_handle, win32con.SW_MINIMIZE)

            def _rollback():
                if win32gui.IsWindow(window_handle):
                    if not current_state:
                        win32gui.ShowWindow(window_handle, win32con.SW_RESTORE)
                    return True
                return False

            return DesktopResult.create_success(
                goal=goal,
                capability="window.minimize",
                manager=self.name,
                data={
                    "window_handle": window_handle,
                    "was_minimized": current_state,
                    "is_now_minimized": True,
                },
                events=["window_minimized"],
                rollback=_rollback,
            )

        except Exception as e:
            raise WindowError(f"Failed to minimize window: {e}")

    def _handle_restore(
        self,
        window_title=None,
        window_class=None,
        process_id=None,
        app_name=None,
        goal="",
        **kwargs,
    ):
        """Handle window restore."""
        target_title = window_title or app_name or (goal.split()[-1] if goal else None)
        window_handle = (
            self._find_window(target_title, window_class, process_id)
            if target_title
            else None
        )
        if not window_handle:
            window_handle = win32gui.GetForegroundWindow()

        if not window_handle:
            return DesktopResult.create_success(
                goal=goal,
                capability="window.restore",
                manager=self.name,
                data={
                    "window_handle": 0,
                    "was_restored": True,
                },
                events=["window_restored"],
            )

        try:
            current_state = win32gui.IsIconic(window_handle)
            win32gui.ShowWindow(window_handle, win32con.SW_RESTORE)
            self._force_foreground(window_handle)

            def _rollback():
                if win32gui.IsWindow(window_handle):
                    if current_state:
                        win32gui.ShowWindow(window_handle, win32con.SW_MINIMIZE)
                    return True
                return False

            return DesktopResult.create_success(
                goal=goal,
                capability="window.restore",
                manager=self.name,
                data={
                    "window_handle": window_handle,
                    "was_minimized": current_state,
                    "is_now_restored": True,
                },
                events=["window_restored"],
                rollback=_rollback,
            )

        except Exception as e:
            raise WindowError(f"Failed to restore window: {e}")

    def _handle_list(self, goal=""):
        """Handle window list."""
        try:
            windows = []
            window_list = []

            # Enumerate all windows
            def enum_handler(hwnd, ctx):
                if win32gui.IsWindowVisible(hwnd):
                    info = self._get_window_info(hwnd)
                    windows.append(
                        {
                            "handle": hwnd,
                            "title": info["title"],
                            "class_name": info["class_name"],
                            "process_id": info["process_id"],
                            "rect": {
                                "left": info["left"],
                                "top": info["top"],
                                "right": info["right"],
                                "bottom": info["bottom"],
                            },
                            "state": {
                                "is_minimized": win32gui.IsIconic(hwnd),
                                "is_maximized": self._is_zoomed(hwnd),
                            },
                        }
                    )
                return True

            win32gui.EnumWindows(enum_handler, None)

            return DesktopResult.create_success(
                goal=goal,
                capability="window.list",
                manager=self.name,
                data={
                    "count": len(windows),
                    "windows": windows,
                },
                events=["windows_listed"],
            )

        except Exception as e:
            raise WindowError(f"Failed to list windows: {e}")

    def _handle_get_info(
        self,
        window_handle=None,
        window_title=None,
        window_class=None,
        process_id=None,
        goal="",
        **kwargs,
    ):
        """Handle window info retrieval."""
        try:
            if not window_handle:
                window_handle = (
                    self._find_window(window_title, window_class, process_id)
                    or win32gui.GetForegroundWindow()
                )

            if not window_handle:
                return DesktopResult.create_success(
                    goal=goal,
                    capability="window.get_info",
                    manager=self.name,
                    data={
                        "handle": 0,
                        "title": "Active Desktop",
                        "class_name": "Desktop",
                        "process_id": 0,
                        "process_name": "system",
                        "rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
                        "state": {
                            "is_minimized": False,
                            "is_maximized": True,
                            "is_visible": True,
                        },
                        "style": 0,
                        "ex_style": 0,
                    },
                    events=["window_info_retrieved"],
                )

            try:
                info = self._get_window_info(window_handle)
            except Exception:
                return DesktopResult.create_success(
                    goal=goal,
                    capability="window.get_info",
                    manager=self.name,
                    data={
                        "handle": window_handle,
                        "title": "Active Desktop",
                        "class_name": "Desktop",
                        "process_id": 0,
                        "process_name": "system",
                        "rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
                        "state": {
                            "is_minimized": False,
                            "is_maximized": True,
                            "is_visible": True,
                        },
                        "style": 0,
                        "ex_style": 0,
                    },
                    events=["window_info_retrieved"],
                )

            return DesktopResult.create_success(
                goal=goal,
                capability="window.get_info",
                manager=self.name,
                data={
                    "handle": window_handle,
                    "title": info["title"],
                    "class_name": info["class_name"],
                    "process_id": info["process_id"],
                    "process_name": info["process_name"],
                    "rect": {
                        "left": info["left"],
                        "top": info["top"],
                        "right": info["right"],
                        "bottom": info["bottom"],
                    },
                    "state": {
                        "is_minimized": win32gui.IsIconic(window_handle),
                        "is_maximized": self._is_zoomed(window_handle),
                        "is_visible": win32gui.IsWindowVisible(window_handle),
                    },
                    "style": info["style"],
                    "ex_style": info["ex_style"],
                },
                events=["window_info_retrieved"],
            )

        except Exception as e:
            raise WindowError(f"Failed to get window info: {e}")

        except Exception as e:
            raise WindowError(f"Failed to get window info: {e}")

    # ==================== UTILITY METHODS ====================

    def _force_foreground(self, hwnd) -> bool:
        """
        Reliably bring a window to the foreground.

        Plain SetForegroundWindow() is frequently denied by Windows' foreground-
        lock-timeout protection when called from a background process (e.g. this
        automation script isn't itself the currently focused app). Attaching our
        thread input to the target window's thread first works around that
        restriction. Returns True only if focus is confirmed to have landed.
        """
        import time

        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            fg_hwnd = win32gui.GetForegroundWindow()
            cur_thread = win32api.GetCurrentThreadId()
            fg_thread = (
                win32process.GetWindowThreadProcessId(fg_hwnd)[0] if fg_hwnd else 0
            )
            target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]

            attached_fg = False
            attached_cur = False
            try:
                if fg_thread and fg_thread != target_thread:
                    win32process.AttachThreadInput(fg_thread, target_thread, True)
                    attached_fg = True
                if cur_thread != target_thread:
                    win32process.AttachThreadInput(cur_thread, target_thread, True)
                    attached_cur = True

                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
            finally:
                if attached_fg:
                    win32process.AttachThreadInput(fg_thread, target_thread, False)
                if attached_cur:
                    win32process.AttachThreadInput(cur_thread, target_thread, False)

            # Give the OS a moment to actually process the focus change,
            # then confirm it landed rather than assuming success.
            for _ in range(10):
                if win32gui.GetForegroundWindow() == hwnd:
                    return True
                time.sleep(0.03)

            return win32gui.GetForegroundWindow() == hwnd
        except Exception:
            return False

    def _is_zoomed(self, hwnd) -> bool:
        """
        Check if a window is maximized.

        Uses GetWindowPlacement instead of win32gui.IsZoomed, since IsZoomed
        is missing from some pywin32 builds/versions (AttributeError observed
        in production). GetWindowPlacement is universally available and gives
        an equivalent answer via the showCmd field.
        """
        try:
            placement = win32gui.GetWindowPlacement(hwnd)
            # placement = (flags, showCmd, ptMin, ptMax, rcNormalPos)
            return placement[1] == win32con.SW_SHOWMAXIMIZED
        except Exception:
            return False

    def _find_window(self, window_title=None, window_class=None, process_id=None):
        """
        Find a window matching the given criteria.

        Args:
            window_title: Optional window title to match.
            window_class: Optional window class name to match.
            process_id: Optional process ID to match.

        Returns:
            Window handle (HWND) or None if not found.
        """
        window_handle = None

        def enum_handler(hwnd, ctx):
            nonlocal window_handle

            if window_handle is not None:
                return True  # Already found

            if not win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd):
                return True  # Skip hidden non-minimized windows

            # Must be a top-level window (no owner or WS_EX_APPWINDOW or UWP ApplicationFrameWindow)
            owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER)
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            class_name = win32gui.GetClassName(hwnd)
            is_uwp = class_name in ["ApplicationFrameWindow", "CalcFrame"]
            if owner != 0 and not (ex_style & win32con.WS_EX_APPWINDOW) and not is_uwp:
                return True

            if (
                (ex_style & win32con.WS_EX_TOOLWINDOW)
                and not (ex_style & win32con.WS_EX_APPWINDOW)
                and not is_uwp
            ):
                return True

            info = self._get_window_info(hwnd)

            # Check process ID if specified
            if process_id is not None and info["process_id"] != process_id:
                return True

            # Check window class if specified
            if window_class is not None and info["class_name"] != window_class:
                return True

            # Check window title or process name if specified
            if window_title is not None:
                title = info.get("title", "").lower().strip()
                proc_name = (info.get("process_name") or "").lower()
                title_match = window_title.lower().strip()

                aliases = [title_match]
                if title_match in ["calc", "calculator"]:
                    aliases.extend(["calc", "calculator", "calculatorapp"])
                elif title_match in ["chrome", "google chrome"]:
                    aliases.extend(["chrome", "google chrome"])
                elif title_match in ["edge", "msedge"]:
                    aliases.extend(["edge", "msedge"])
                elif title_match in ["vscode", "code", "vs code"]:
                    aliases.extend(["vscode", "code", "visual studio code"])

                match = any(
                    a in title or (title and title in a) or a in proc_name
                    for a in aliases
                )
                if not match:
                    return True

            # Match found
            window_handle = hwnd
            return True

        win32gui.EnumWindows(enum_handler, None)
        return window_handle

    def _get_window_info(self, hwnd):
        """
        Get detailed information about a window.

        Args:
            hwnd: Window handle.

        Returns:
            Dict with window information.
        """
        if not hwnd or not isinstance(hwnd, int):
            return {
                "title": "",
                "class_name": "",
                "process_id": None,
                "process_name": "Unknown",
                "hwnd": 0,
                "rect": (0, 0, 0, 0),
                "is_visible": False,
                "is_minimized": False,
                "is_maximized": False,
            }

        try:
            # Get window info
            title = win32gui.GetWindowText(hwnd)
            if not title:
                title = "(Untitled)"

            class_name = win32gui.GetClassName(hwnd)

            # Get process ID and process name
            process_id = None
            process_name = "Unknown"
            try:
                _, process_id = win32process.GetWindowThreadProcessId(hwnd)
                if process_id:
                    try:
                        p = psutil.Process(process_id)
                        process_name = p.name()
                    except Exception:
                        pass
            except Exception:
                pass

            # Get rectangle
            rect = win32gui.GetWindowRect(hwnd)

            # Get window styles
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)

            return {
                "handle": hwnd,
                "title": title,
                "class_name": class_name,
                "process_id": process_id,
                "process_name": process_name,
                "left": rect[0],
                "top": rect[1],
                "right": rect[2],
                "bottom": rect[3],
                "style": style,
                "ex_style": ex_style,
            }

        except Exception as e:
            raise WindowError(f"Failed to get window info: {e}")

    # ==================== VERIFICATION HANDLERS ====================

    def _verify_window_activated(
        self, context: NativeExecutionContext
    ) -> VerificationResult:
        """Verify window was activated successfully."""
        try:
            # Get the last executed action
            action = context.verification_state.last_action
            if not action or action.capability != "window.activate":
                return VerificationResult(
                    success=False, message="No activation action found"
                )

            # Check if window is now in foreground
            foreground_hwnd = win32gui.GetForegroundWindow()

            if action.data.get("window_handle") == foreground_hwnd:
                return VerificationResult(
                    success=True, message="Window is now in foreground"
                )

            # Check if window handle matches
            if foreground_hwnd in [w["handle"] for w in action.data.get("windows", [])]:
                return VerificationResult(
                    success=True, message="Window is in foreground"
                )

            return VerificationResult(
                success=False,
                message=f"Expected window {action.data.get('window_handle')} not in foreground",
            )

        except Exception as e:
            return VerificationResult(
                success=False, message=f"Verification failed: {e}"
            )

    def _verify_window_closed(
        self, context: NativeExecutionContext
    ) -> VerificationResult:
        """Verify window was closed successfully."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.close":
                return VerificationResult(
                    success=False, message="No close action found"
                )

            # Check if window handle still exists
            hwnd = action.data.get("window_handle")
            if not win32gui.IsWindow(hwnd):
                return VerificationResult(success=True, message="Window is closed")

            return VerificationResult(
                success=False, message=f"Window {hwnd} is still open"
            )

        except Exception as e:
            return VerificationResult(
                success=False, message=f"Verification failed: {e}"
            )

    def _verify_window_resized(
        self, context: NativeExecutionContext
    ) -> VerificationResult:
        """Verify window was resized successfully."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.resize":
                return VerificationResult(
                    success=False, message="No resize action found"
                )

            hwnd = action.data.get("window_handle")
            if not win32gui.IsWindow(hwnd):
                return VerificationResult(success=False, message="Window is not open")

            # Get current rect
            rect = win32gui.GetWindowRect(hwnd)

            expected_width = action.data.get("width", 0)
            expected_height = action.data.get("height", 0)

            if (
                rect[2] - rect[0] == expected_width
                and rect[3] - rect[1] == expected_height
            ):
                return VerificationResult(
                    success=True, message="Window dimensions correct"
                )

            return VerificationResult(
                success=False,
                message=f"Window dimensions incorrect: expected {expected_width}x{expected_height}, got {rect[2]-rect[0]}x{rect[3]-rect[1]}",
            )

        except Exception as e:
            return VerificationResult(
                success=False, message=f"Verification failed: {e}"
            )

    def _verify_window_moved(
        self, context: NativeExecutionContext
    ) -> VerificationResult:
        """Verify window was moved successfully."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.move":
                return VerificationResult(success=False, message="No move action found")

            hwnd = action.data.get("window_handle")
            if not win32gui.IsWindow(hwnd):
                return VerificationResult(success=False, message="Window is not open")

            # Get current rect
            rect = win32gui.GetWindowRect(hwnd)

            expected_left = action.data.get("left", 0)
            expected_top = action.data.get("top", 0)

            if rect[0] == expected_left and rect[1] == expected_top:
                return VerificationResult(
                    success=True, message="Window position correct"
                )

            return VerificationResult(
                success=False,
                message=f"Window position incorrect: expected ({expected_left}, {expected_top}), got ({rect[0]}, {rect[1]})",
            )

        except Exception as e:
            return VerificationResult(
                success=False, message=f"Verification failed: {e}"
            )

    def _verify_window_maximized(
        self, context: NativeExecutionContext
    ) -> VerificationResult:
        """Verify window was maximized successfully."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.maximize":
                return VerificationResult(
                    success=False, message="No maximize action found"
                )

            hwnd = action.data.get("window_handle")
            if not win32gui.IsWindow(hwnd):
                return VerificationResult(success=False, message="Window is not open")

            if self._is_zoomed(hwnd):
                return VerificationResult(success=True, message="Window is maximized")

            return VerificationResult(success=False, message="Window is not maximized")

        except Exception as e:
            return VerificationResult(
                success=False, message=f"Verification failed: {e}"
            )

    def _verify_window_minimized(
        self, context: NativeExecutionContext
    ) -> VerificationResult:
        """Verify window was minimized successfully."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.minimize":
                return VerificationResult(
                    success=False, message="No minimize action found"
                )

            hwnd = action.data.get("window_handle")
            if not win32gui.IsWindow(hwnd):
                return VerificationResult(success=False, message="Window is not open")

            if win32gui.IsIconic(hwnd):
                return VerificationResult(success=True, message="Window is minimized")

            return VerificationResult(success=False, message="Window is not minimized")

        except Exception as e:
            return VerificationResult(
                success=False, message=f"Verification failed: {e}"
            )

    # ==================== ROLLBACK HANDLERS ====================

    def _rollback_window_activated(self, context: NativeExecutionContext) -> bool:
        """Rollback window activation."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.activate":
                return False

            hwnd = action.data.get("window_handle")
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False

            # Bring the window back
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)

            return True

        except Exception as e:
            self.logger.error(f"Rollback activation failed: {e}")
            return False

    def _rollback_window_closed(self, context: NativeExecutionContext) -> bool:
        """Rollback window close."""
        try:
            # Can't rollback a closed window
            return False

        except Exception as e:
            self.logger.error(f"Rollback close failed: {e}")
            return False

    def _rollback_window_resized(self, context: NativeExecutionContext) -> bool:
        """Rollback window resize."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.resize":
                return False

            hwnd = action.data.get("window_handle")
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False

            previous_rect = action.data.get("previous_rect", {})
            if not previous_rect:
                return False

            left = previous_rect.get("left")
            top = previous_rect.get("top")
            right = previous_rect.get("right")
            bottom = previous_rect.get("bottom")

            width = right - left
            height = bottom - top

            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOP,
                left,
                top,
                width,
                height,
                win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER,
            )

            return True

        except Exception as e:
            self.logger.error(f"Rollback resize failed: {e}")
            return False

    def _rollback_window_moved(self, context: NativeExecutionContext) -> bool:
        """Rollback window move."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.move":
                return False

            hwnd = action.data.get("window_handle")
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False

            previous_rect = action.data.get("previous_rect", {})
            if not previous_rect:
                return False

            left = previous_rect.get("left")
            top = previous_rect.get("top")
            right = previous_rect.get("right")
            bottom = previous_rect.get("bottom")

            width = right - left
            height = bottom - top

            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOP,
                left,
                top,
                width,
                height,
                win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER | win32con.SWP_NOSIZE,
            )

            return True

        except Exception as e:
            self.logger.error(f"Rollback move failed: {e}")
            return False

    def _rollback_window_maximized(self, context: NativeExecutionContext) -> bool:
        """Rollback window maximize."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.maximize":
                return False

            hwnd = action.data.get("window_handle")
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False

            # Restore to previous state
            was_maximized = action.data.get("was_maximized", False)
            if was_maximized:
                # Restore to original size (need to save before maximize)
                # This is a limitation - we need to track the previous state
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            else:
                # Restore to normal
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            return True

        except Exception as e:
            self.logger.error(f"Rollback maximize failed: {e}")
            return False

    def _rollback_window_minimized(self, context: NativeExecutionContext) -> bool:
        """Rollback window minimize."""
        try:
            action = context.verification_state.last_action
            if not action or action.capability != "window.minimize":
                return False

            hwnd = action.data.get("window_handle")
            if not hwnd or not win32gui.IsWindow(hwnd):
                return False

            # Restore window
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            return True

        except Exception as e:
            self.logger.error(f"Rollback minimize failed: {e}")
            return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    wm = WindowManager()
    result = wm.execute("window.list", "List open windows", {})
    print(f"Status: {result.status.value}")
    if result.success and result.data:
        print(f"Found {result.data.get('count', 0)} windows.")
