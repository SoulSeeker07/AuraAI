"""
AuraAI Global & Context-Aware Win32 Hotkey Service
==================================================
Location: src/tools/hotkey_service.py

Uses native Windows Win32 RegisterHotKey API with a dedicated message loop:
1. Alt + Space: Toggle Aura Chat HUD from anywhere on Windows (overriding system menu).
2. Ctrl + Q: Closes active terminal window/tab (Command Prompt, PowerShell, Windows Terminal, or VS Code terminal).
"""

import sys
import ctypes
import ctypes.wintypes
import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Win32 Constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
VK_SPACE = 0x20
VK_Q = 0x51
VK_N = 0x4E
VK_V = 0x56
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

HOTKEY_ALT_SPACE = 9001
HOTKEY_CTRL_Q = 9002
HOTKEY_ALT_N = 9003
HOTKEY_ALT_V = 9004

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class GlobalHotkeyService:
    """System-wide global hotkey and key-hold listener for AuraAI."""

    _instance: Optional["GlobalHotkeyService"] = None

    def __init__(self, on_toggle_chat: Optional[Callable[[], None]] = None):
        self.on_toggle_chat = on_toggle_chat
        self._running: bool = False
        self._hold_start: dict[str, float] = {}
        self._hold_triggered: set[str] = set()

    @classmethod
    def get_instance(cls, on_toggle_chat: Optional[Callable[[], None]] = None) -> "GlobalHotkeyService":
        if cls._instance is None:
            cls._instance = GlobalHotkeyService(on_toggle_chat=on_toggle_chat)
        elif on_toggle_chat is not None:
            cls._instance.on_toggle_chat = on_toggle_chat
        return cls._instance

    def start(self) -> None:
        """Starts global keyboard hooks using low-level Windows hook."""
        if self._running:
            return

        self._running = True
        try:
            import keyboard
            import time

            def _on_key_event(event):
                if not self._running:
                    return

                key_name = (event.name or "").lower()
                is_target_key = key_name in (
                    "right ctrl", "right control", "ctrl", "control",
                    "right alt", "alt gr", "f8", "pause"
                )

                if is_target_key:
                    if event.event_type == "down":
                        now = time.time()
                        if key_name not in self._hold_start:
                            self._hold_start[key_name] = now
                        elif (now - self._hold_start[key_name] >= 1.0) and (key_name not in self._hold_triggered):
                            self._hold_triggered.add(key_name)
                            logger.info(f"[GlobalHotkeyService] Key '{key_name}' held for 1s -> Triggering Voice Listening!")
                            try:
                                from gui.signals import app_signals
                                app_signals.trigger_voice_listening.emit()
                            except Exception as e:
                                logger.debug(f"[GlobalHotkeyService] Signal error: {e}")
                    elif event.event_type == "up":
                        self._hold_start.pop(key_name, None)
                        self._hold_triggered.discard(key_name)

            keyboard.hook(_on_key_event)

            # Register Instant Hotkeys
            keyboard.add_hotkey("alt+v", self._on_trigger_listening, suppress=False)
            keyboard.add_hotkey("alt+n", self._on_alt_n, suppress=False)
            keyboard.add_hotkey("alt+space", self._on_alt_space, suppress=False)

            logger.info("[GlobalHotkeyService] Global keyboard hooks registered successfully.")
        except Exception as exc:
            logger.error(f"[GlobalHotkeyService] Failed to initialize keyboard hooks: {exc}")

    def stop(self) -> None:
        """Stops global keyboard hooks."""
        if not self._running:
            return

        self._running = False
        try:
            import keyboard
            keyboard.unhook_all()
        except Exception:
            pass
        logger.info("[GlobalHotkeyService] Stopped global hotkey service.")

    def _on_trigger_listening(self) -> None:
        """Triggered on Alt+V globally."""
        logger.info("[GlobalHotkeyService] Alt+V pressed -> Triggering Voice Listening.")
        try:
            from gui.signals import app_signals
            app_signals.trigger_voice_listening.emit()
        except Exception as e:
            logger.debug(f"[GlobalHotkeyService] Signal error: {e}")

    def _msg_loop(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()

        # 1. Register Alt + Space (ID 9001)
        r_alt_space = user32.RegisterHotKey(
            None,
            HOTKEY_ALT_SPACE,
            MOD_ALT | MOD_NOREPEAT,
            VK_SPACE,
        )
        if r_alt_space:
            logger.info("[GlobalHotkeyService] Native Win32 Alt+Space successfully registered.")
        else:
            logger.warning(f"[GlobalHotkeyService] Win32 Alt+Space registration failed (Error: {ctypes.GetLastError()}).")

        # 2. Register Ctrl + Q (ID 9002)
        r_ctrl_q = user32.RegisterHotKey(
            None,
            HOTKEY_CTRL_Q,
            MOD_CONTROL | MOD_NOREPEAT,
            VK_Q,
        )
        if r_ctrl_q:
            logger.info("[GlobalHotkeyService] Native Win32 Ctrl+Q successfully registered.")
        else:
            logger.warning(f"[GlobalHotkeyService] Win32 Ctrl+Q registration failed (Error: {ctypes.GetLastError()}).")

        # 3. Register Alt + N (ID 9003) - Voice Notch
        user32.RegisterHotKey(
            None,
            HOTKEY_ALT_N,
            MOD_ALT | MOD_NOREPEAT,
            VK_N,
        )

        # 4. Register Alt + V (ID 9004) - Voice Toggle
        user32.RegisterHotKey(
            None,
            HOTKEY_ALT_V,
            MOD_ALT | MOD_NOREPEAT,
            VK_V,
        )

        # Win32 Message Loop
        msg = ctypes.wintypes.MSG()
        while self._running:
            res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if res <= 0:
                break

            if msg.message == WM_HOTKEY:
                hotkey_id = msg.wParam
                if hotkey_id == HOTKEY_ALT_SPACE:
                    self._on_alt_space()
                elif hotkey_id == HOTKEY_CTRL_Q:
                    self._on_ctrl_q()
                elif hotkey_id in (HOTKEY_ALT_N, HOTKEY_ALT_V):
                    self._on_alt_n()

            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # Cleanup
        user32.UnregisterHotKey(None, HOTKEY_ALT_SPACE)
        user32.UnregisterHotKey(None, HOTKEY_CTRL_Q)
        user32.UnregisterHotKey(None, HOTKEY_ALT_N)
        user32.UnregisterHotKey(None, HOTKEY_ALT_V)

    def _on_alt_n(self) -> None:
        """Triggered on Alt+N or Alt+V anywhere on Windows."""
        logger.info("[GlobalHotkeyService] Alt+N/Alt+V detected -> Toggling Voice Notch.")
        try:
            from gui.signals import app_signals
            app_signals.toggle_voice_notch.emit()
        except Exception as e:
            logger.debug(f"[GlobalHotkeyService] Signal emit error: {e}")

    def _on_alt_space(self) -> None:
        """Triggered on Alt+Space anywhere."""
        logger.info("[GlobalHotkeyService] Alt+Space detected -> Toggling Chat HUD.")
        try:
            from gui.signals import app_signals
            app_signals.toggle_chat_overlay.emit()
        except Exception as e:
            logger.debug(f"[GlobalHotkeyService] Signal emit error: {e}")

        if self.on_toggle_chat:
            try:
                self.on_toggle_chat()
            except Exception as e:
                logger.debug(f"[GlobalHotkeyService] on_toggle_chat callback error: {e}")

    def _on_ctrl_q(self) -> None:
        """Triggered on Ctrl+Q. Only acts if active window is a terminal/console."""
        try:
            import win32gui
            import win32process
            import win32con

            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return

            title = win32gui.GetWindowText(hwnd).lower()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            proc_name = ""
            try:
                import psutil
                if pid and psutil.pid_exists(pid):
                    proc_name = psutil.Process(pid).name().lower()
            except Exception:
                pass

            is_terminal = (
                any(t in proc_name for t in ("cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal.exe", "conhost.exe", "bash.exe"))
                or any(t in title for t in ("command prompt", "powershell", "windows terminal", "cmd.exe", "pwsh", "mingw", "git bash"))
                or ("visual studio code" in title and "terminal" in title)
                or ("code.exe" in proc_name and "terminal" in title)
            )

            if is_terminal:
                logger.info(f"[GlobalHotkeyService] Ctrl+Q closing terminal: '{title}' ({proc_name}).")
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            else:
                # If not a terminal, re-emit or ignore without closing normal apps
                logger.debug(f"[GlobalHotkeyService] Ctrl+Q ignored: '{title}' is not a terminal.")
        except Exception as e:
            logger.debug(f"[GlobalHotkeyService] Ctrl+Q handler notice: {e}")
