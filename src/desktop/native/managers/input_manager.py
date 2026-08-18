"""
Input Simulation Manager — Keyboard & Mouse Automation Engine
Location: src/desktop/native/managers/input_manager.py

Provides synthetic keyboard and mouse input using Win32 SendInput API.
This is the #1 critical capability for agentic computer-use AI.

Uses ctypes directly — zero external dependencies.
"""

import ctypes
import ctypes.wintypes
import logging
import time
from typing import Any

from ..desktop_result import DesktopResult
from .base_manager import BaseNativeManager, HealthCheckResult, HealthStatus

logger = logging.getLogger(__name__)

# ── Win32 Constants ──
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
WHEEL_DELTA = 120

# Virtual Key code mapping
VK_MAP: dict[str, int] = {
    "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "return": 0x0D,
    "shift": 0xA0, "ctrl": 0xA2, "control": 0xA2, "alt": 0xA4, "menu": 0xA4,
    "pause": 0x13, "capslock": 0x14, "escape": 0x1B, "esc": 0x1B,
    "space": 0x20, "pageup": 0x21, "pagedown": 0x22, "end": 0x23,
    "home": 0x24, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "printscreen": 0x2C, "insert": 0x2D, "delete": 0x2E, "del": 0x2E,
    "lwin": 0x5B, "rwin": 0x5C, "win": 0x5B, "apps": 0x5D,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
    "f11": 0x7A, "f12": 0x7B, "numlock": 0x90, "scrolllock": 0x91,
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
    "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
    "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
    "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
    "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59, "z": 0x5A,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
}


# ── Win32 Structures ──
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.wintypes.LONG),
        ("dy", ctypes.wintypes.LONG),
        ("mouseData", ctypes.wintypes.DWORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD),
        ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUTunion(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.wintypes.DWORD), ("union", _INPUTunion)]


def _send_input(*inputs: INPUT) -> int:
    """Send input events via Win32 SendInput."""
    arr = (INPUT * len(inputs))(*inputs)
    return ctypes.windll.user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def _get_screen_size() -> tuple[int, int]:
    """Get primary screen resolution."""
    return (
        ctypes.windll.user32.GetSystemMetrics(0),
        ctypes.windll.user32.GetSystemMetrics(1),
    )


def _abs_coords(x: int, y: int) -> tuple[int, int]:
    """Convert pixel coordinates to 0-65535 absolute range."""
    w, h = _get_screen_size()
    return int(x * 65535 / w), int(y * 65535 / h)


class InputFailsafeException(Exception):
    """Raised when the user activates the physical mouse corner-trap failsafe."""
    pass


class InputManager(BaseNativeManager):
    """
    Keyboard & Mouse Simulation Manager.

    Provides synthetic input using Win32 SendInput API for true agentic
    computer-use capability with hardware failsafes, coordinate clamping,
    and sticky-key auto-release.
    """

    NAME = "input"
    VERSION = "1.0"
    PRIORITY = 5  # Highest priority — needed by ScreenActionLoop
    DEPENDENCIES: list[str] = []

    # Safety: minimum delay between destructive actions (ms)
    _MIN_ACTION_DELAY_MS = 50
    _CORNER_FAILSAFE_MARGIN = 5  # pixels

    def __init__(self):
        super().__init__()
        self._last_action_time: float = 0.0
        self._initialized = False
        self.failsafe_enabled: bool = True
        self._held_keys: set[int] = set()
        self._held_mouse_buttons: set[int] = set()
        self._emergency_aborted: bool = False

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def capabilities(self) -> list[str]:
        return [
            "input.click", "input.double_click", "input.right_click",
            "input.drag", "input.scroll", "input.type_text",
            "input.hotkey", "input.key_press", "input.key_down",
            "input.key_up", "input.move_mouse", "input.mouse_position",
            "input.emergency_stop", "input.release_held_keys",
        ]

    def initialize(self) -> bool:
        self._initialized = True
        self._emergency_aborted = False
        return True

    def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            manager_name=self.name,
            status=HealthStatus.HEALTHY,
            total_capabilities=len(self.capabilities),
            available_capabilities=len(self.capabilities),
            details={
                "initialized": self._initialized,
                "backend": "ctypes/SendInput",
                "failsafe_enabled": self.failsafe_enabled,
                "held_keys_count": len(self._held_keys),
            },
        )

    def shutdown(self) -> None:
        self.emergency_stop()
        self._initialized = False

    def _check_failsafe(self) -> None:
        """PyAutoGUI-style corner-trap failsafe."""
        if not self.failsafe_enabled:
            return
        pos = self._mouse_position()
        w, h = _get_screen_size()
        m = self._CORNER_FAILSAFE_MARGIN
        # Check if cursor is in any of the 4 screen corners
        in_top_left = pos[0] <= m and pos[1] <= m
        in_top_right = pos[0] >= w - m and pos[1] <= m
        in_bottom_left = pos[0] <= m and pos[1] >= h - m
        in_bottom_right = pos[0] >= w - m and pos[1] >= h - m

        if in_top_left or in_top_right or in_bottom_left or in_bottom_right:
            self.emergency_stop()
            raise InputFailsafeException(
                f"Input failsafe triggered at coordinates {pos}. All synthetic actions aborted."
            )

    def _clamp_coords(self, x: int, y: int) -> tuple[int, int]:
        """Clamp coordinates within screen resolution bounds."""
        w, h = _get_screen_size()
        cx = max(0, min(int(x), w - 1))
        cy = max(0, min(int(y), h - 1))
        return cx, cy

    def _release_all_held(self) -> None:
        """Emergency release for all held modifier keys and mouse buttons."""
        # Release held keys
        for vk in list(self._held_keys):
            try:
                self._key_event(vk, up=True)
            except Exception:
                pass
        self._held_keys.clear()

        # Release standard modifiers just in case
        for mod_vk in (0xA0, 0xA2, 0xA4, 0x5B, 0x5C):  # Shift, Ctrl, Alt, LWin, RWin
            try:
                self._key_event(mod_vk, up=True)
            except Exception:
                pass

        # Release mouse buttons
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.union.mi.dwFlags = MOUSEEVENTF_LEFTUP | MOUSEEVENTF_RIGHTUP | MOUSEEVENTF_MIDDLEUP
        _send_input(inp)
        self._held_mouse_buttons.clear()

    def emergency_stop(self) -> None:
        """Immediately abort all input and release held state."""
        self._emergency_aborted = True
        self._release_all_held()
        logger.warning("InputManager emergency_stop triggered: all inputs released.")

    def _throttle(self) -> None:
        """Enforce minimum delay between actions."""
        now = time.monotonic()
        elapsed_ms = (now - self._last_action_time) * 1000
        if elapsed_ms < self._MIN_ACTION_DELAY_MS:
            time.sleep((self._MIN_ACTION_DELAY_MS - elapsed_ms) / 1000)
        self._last_action_time = time.monotonic()

    # ── Core Input Methods ──

    def _mouse_event(self, x: int, y: int, flags: int, data: int = 0) -> None:
        self._check_failsafe()
        cx, cy = self._clamp_coords(x, y)
        ax, ay = _abs_coords(cx, cy)
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.union.mi.dx = ax
        inp.union.mi.dy = ay
        inp.union.mi.mouseData = data
        inp.union.mi.dwFlags = flags | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE
        _send_input(inp)


    def _click(self, x: int, y: int) -> None:
        self._throttle()
        self._mouse_event(x, y, MOUSEEVENTF_LEFTDOWN)
        time.sleep(0.02)
        self._mouse_event(x, y, MOUSEEVENTF_LEFTUP)

    def _double_click(self, x: int, y: int) -> None:
        self._click(x, y)
        time.sleep(0.05)
        self._click(x, y)

    def _right_click(self, x: int, y: int) -> None:
        self._throttle()
        self._mouse_event(x, y, MOUSEEVENTF_RIGHTDOWN)
        time.sleep(0.02)
        self._mouse_event(x, y, MOUSEEVENTF_RIGHTUP)

    def _drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> None:
        self._throttle()
        self._check_failsafe()
        self._mouse_event(x1, y1, MOUSEEVENTF_LEFTDOWN)
        steps = max(10, int(duration * 60))
        try:
            for i in range(1, steps + 1):
                self._check_failsafe()
                frac = i / steps
                cx, cy = int(x1 + (x2 - x1) * frac), int(y1 + (y2 - y1) * frac)
                self._mouse_event(cx, cy, 0)
                time.sleep(duration / steps)
        finally:
            self._mouse_event(x2, y2, MOUSEEVENTF_LEFTUP)

    def _scroll(self, direction: str = "down", amount: int = 3) -> None:
        self._throttle()
        delta = -WHEEL_DELTA * amount if direction.lower() == "down" else WHEEL_DELTA * amount
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.union.mi.mouseData = delta
        inp.union.mi.dwFlags = MOUSEEVENTF_WHEEL
        _send_input(inp)

    def _move_mouse(self, x: int, y: int) -> None:
        self._throttle()
        ax, ay = _abs_coords(x, y)
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.union.mi.dx = ax
        inp.union.mi.dy = ay
        inp.union.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        _send_input(inp)

    def _mouse_position(self) -> tuple[int, int]:
        point = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        return (point.x, point.y)

    def _key_event(self, vk: int, up: bool = False) -> None:
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wVk = vk
        inp.union.ki.dwFlags = KEYEVENTF_KEYUP if up else 0
        _send_input(inp)

    def _key_press(self, key: str) -> None:
        self._throttle()
        vk = VK_MAP.get(key.lower())
        if vk is None:
            if len(key) == 1:
                vk = ctypes.windll.user32.VkKeyScanW(ord(key)) & 0xFF
            else:
                raise ValueError(f"Unknown key: {key}")
        self._key_event(vk)
        time.sleep(0.02)
        self._key_event(vk, up=True)

    def _type_text(self, text: str) -> None:
        self._throttle()
        for char in text:
            # UTF-16-LE encoding splits non-BMP characters (like emoji) into surrogate pairs
            utf16_bytes = char.encode("utf-16le")
            for i in range(0, len(utf16_bytes), 2):
                code_unit = int.from_bytes(utf16_bytes[i : i + 2], "little")
                inp_down = INPUT()
                inp_down.type = INPUT_KEYBOARD
                inp_down.union.ki.wScan = code_unit
                inp_down.union.ki.dwFlags = KEYEVENTF_UNICODE
                inp_up = INPUT()
                inp_up.type = INPUT_KEYBOARD
                inp_up.union.ki.wScan = code_unit
                inp_up.union.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
                _send_input(inp_down, inp_up)
            time.sleep(0.01)

    def _hotkey(self, keys_str: str) -> None:
        """Execute a hotkey combo like 'ctrl+c', 'alt+tab', 'ctrl+shift+s'."""
        self._throttle()
        parts = [k.strip().lower() for k in keys_str.split("+")]
        vk_codes = []
        for part in parts:
            vk = VK_MAP.get(part)
            if vk is None and len(part) == 1:
                vk = ctypes.windll.user32.VkKeyScanW(ord(part)) & 0xFF
            if vk is None:
                raise ValueError(f"Unknown key in hotkey: {part}")
            vk_codes.append(vk)
        for vk in vk_codes:
            self._key_event(vk)
            time.sleep(0.02)
        for vk in reversed(vk_codes):
            self._key_event(vk, up=True)
            time.sleep(0.02)

    # ── Execute Dispatcher ──

    def execute(
        self, capability: str, goal: str = "",
        arguments: dict[str, Any] | None = None, **kwargs: Any,
    ) -> DesktopResult:
        args = arguments or {}
        cap = capability.lower()
        try:
            if cap == "input.mouse_position":
                pos = self._mouse_position()
                return DesktopResult.create_success(
                    goal=goal, capability=capability, manager=self.name,
                    data={"x": pos[0], "y": pos[1]},
                )
            elif cap == "input.click":
                self._click(int(args.get("x", 0)), int(args.get("y", 0)))
            elif cap == "input.double_click":
                self._double_click(int(args.get("x", 0)), int(args.get("y", 0)))
            elif cap == "input.right_click":
                self._right_click(int(args.get("x", 0)), int(args.get("y", 0)))
            elif cap == "input.drag":
                self._drag(int(args.get("x1", 0)), int(args.get("y1", 0)),
                           int(args.get("x2", 0)), int(args.get("y2", 0)),
                           float(args.get("duration", 0.5)))
            elif cap == "input.scroll":
                self._scroll(args.get("direction", "down"), int(args.get("amount", 3)))
            elif cap == "input.move_mouse":
                self._move_mouse(int(args.get("x", 0)), int(args.get("y", 0)))
            elif cap == "input.type_text":
                text = args.get("text", "")
                if not text:
                    return DesktopResult.create_failure(
                        goal=goal, capability=capability, manager=self.name,
                        error="No text provided for type_text")
                self._type_text(text)
            elif cap == "input.hotkey":
                keys = args.get("keys", "")
                if not keys:
                    return DesktopResult.create_failure(
                        goal=goal, capability=capability, manager=self.name,
                        error="No keys provided for hotkey")
                self._hotkey(keys)
            elif cap == "input.key_press":
                self._key_press(args.get("key", ""))
            elif cap == "input.key_down":
                vk = VK_MAP.get(args.get("key", "").lower())
                if vk:
                    self._key_event(vk)
                else:
                    return DesktopResult.create_failure(
                        goal=goal, capability=capability, manager=self.name,
                        error=f"Unknown key: {args.get('key')}")
            elif cap == "input.key_up":
                vk = VK_MAP.get(args.get("key", "").lower())
                if vk:
                    self._key_event(vk, up=True)
                else:
                    return DesktopResult.create_failure(
                        goal=goal, capability=capability, manager=self.name,
                        error=f"Unknown key: {args.get('key')}")
            elif cap == "input.emergency_stop":
                self.emergency_stop()
                return DesktopResult.create_success(
                    goal=goal, capability=capability, manager=self.name,
                    data={"emergency_stop": True, "aborted": True},
                    events=["emergency_stop_executed"],
                )
            elif cap == "input.release_held_keys":
                self._release_all_held()
                return DesktopResult.create_success(
                    goal=goal, capability=capability, manager=self.name,
                    data={"released": True},
                    events=["held_keys_released"],
                )
            else:
                return DesktopResult.create_failure(
                    goal=goal, capability=capability, manager=self.name,
                    error=f"Unsupported input capability: {capability}")


            return DesktopResult.create_success(
                goal=goal, capability=capability, manager=self.name,
                data={"action": cap, "arguments": args},
                events=[f"{cap}_executed"],
            )
        except Exception as exc:
            logger.error(f"InputManager.{cap} failed: {exc}")
            return DesktopResult.create_failure(
                goal=goal, capability=capability, manager=self.name,
                error=f"Input simulation failed: {exc}")
