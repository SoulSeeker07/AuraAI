"""
Execution Policy
Location: src/core/orchestration/execution_policy.py

Inserts between Planner and DesktopBackend to enforce universal OS-action rules:

    Intent → Planner → ExecutionPolicy.evaluate(goal, app_name, world_snap)
      → REUSE_EXISTING    → WindowManager.activate (bring to front)
      → LAUNCH_NEW        → WindowManager.app_open (new process)
      → ASK_USER          → Confirmation prompt stored as pending
      → CONFIRMED_LAUNCH  → User said yes, launch new instance
      → FAIL              → Error response

Universal behavior:
    Open Chrome    → already running → Focus existing? (yes/no)
    Open VS Code   → already running → Focus existing workspace?
    Open Notepad   → already running → Open another instance?
    Open Spotify   → already running → Resume existing session?
    Open Calculator → already open  → Bring to front?
"""

from __future__ import annotations

import hashlib
import logging
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .autonomy_mode import AutonomyLevel

logger = logging.getLogger(__name__)

# Request/Coroutine-scoped Autonomy Level context
_autonomy_level_ctx: ContextVar[AutonomyLevel] = ContextVar(
    "_autonomy_level_ctx", default=AutonomyLevel.ASSISTED
)


class PolicyAction(Enum):
    """What the execution policy decided to do."""

    REUSE_EXISTING = "reuse_existing"
    LAUNCH_NEW = "launch_new"
    ASK_USER = "ask_user"
    CONFIRMED_LAUNCH = "confirmed_launch"
    FAIL = "fail"


@dataclass
class PolicyDecision:
    """Decision returned by ExecutionPolicy.evaluate()."""

    action: PolicyAction
    message: str
    app_name: str
    window_count: int = 0
    confirmation_key: str = ""
    hwnd: int | None = None


@dataclass
class PendingConfirmation:
    """A stored pending confirmation waiting for user yes/no."""

    key: str
    app_name: str
    goal: str
    created_at: float = field(default_factory=time.monotonic)

    def is_expired(self, ttl_seconds: float = 120.0) -> bool:
        return (time.monotonic() - self.created_at) > ttl_seconds


class ExecutionPolicy:
    """
    Singleton that evaluates desktop action requests, autonomy modes (ASK, ASSISTED, AUTONOMOUS),
    and action risk levels with request-scoped ContextVar isolation.

    Holds pending confirmations across turns.
    """

    _instance: ExecutionPolicy | None = None

    def __init__(self) -> None:
        self._pending: dict[str, PendingConfirmation] = {}

    @classmethod
    def get_instance(cls) -> ExecutionPolicy:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # ── Autonomy Level API (Coroutine & Thread-Safe via ContextVar) ──────────

    def set_autonomy_level(self, level: Any) -> Token:
        if isinstance(level, str):
            level = AutonomyLevel(level.lower())
        token = _autonomy_level_ctx.set(level)
        logger.info(f"ExecutionPolicy autonomy level set to: {level.value} (ctx token: {token})")
        return token

    def reset_autonomy_level(self, token: Token) -> None:
        """Reset the request-scoped autonomy level using the token returned by set_autonomy_level."""
        try:
            _autonomy_level_ctx.reset(token)
        except Exception as e:
            logger.warning(f"Could not reset autonomy level token: {e}")

    def get_autonomy_level(self) -> AutonomyLevel:
        return _autonomy_level_ctx.get()

    def evaluate_action(
        self, engine: str, action: str, params: dict[str, Any] | None = None
    ) -> PolicyDecision:
        """
        Evaluate any engine action against the active autonomy mode and action risk level.

        Returns PolicyDecision with PolicyAction.ASK_USER if confirmation is required.
        """
        from .autonomy_mode import classify_action_risk, should_require_confirmation

        autonomy_level = self.get_autonomy_level()
        risk = classify_action_risk(engine, action, params)
        requires_conf = should_require_confirmation(autonomy_level, risk)

        if requires_conf:
            key = self._make_key(f"{engine}_{action}_{params}")
            msg = (
                f"Action [{engine}] '{action}' carries {risk.value.upper()} risk under "
                f"{autonomy_level.value.upper()} autonomy. Require confirmation? (yes/no)"
            )
            self._pending[key] = PendingConfirmation(
                key=key, app_name=f"{engine}.{action}", goal=f"Execute {action}"
            )
            logger.info(f"ExecutionPolicy action blocked: [{engine}] {action} (Risk: {risk.value}) → ASK_USER")
            return PolicyDecision(
                action=PolicyAction.ASK_USER,
                message=msg,
                app_name=f"{engine}.{action}",
                confirmation_key=key,
            )

        return PolicyDecision(
            action=PolicyAction.LAUNCH_NEW,
            message=f"Action [{engine}] '{action}' approved under {autonomy_level.value.upper()} autonomy.",
            app_name=f"{engine}.{action}",
        )

    # ── Public API ──────────────────────────────────────────────────────────

    def evaluate(
        self,
        goal: str,
        app_name: str,
        world_snap: Any | None = None,
        force_new: bool = False,
    ) -> PolicyDecision:
        """
        Evaluate an app_open intent against live OS world state.

        Priority:
        1. force_new is True or goal requests new instance → LAUNCH_NEW
        2. App NOT running → LAUNCH_NEW
        3. App IS running  → count real EnumWindows HWNDs → ASK_USER
        """
        if force_new or any(
            w in goal.lower()
            for w in ["another", "new", "second", "extra", "different"]
        ):
            logger.debug(
                f"ExecutionPolicy: '{app_name}' force_new/explicit new instance → LAUNCH_NEW"
            )
            return PolicyDecision(
                action=PolicyAction.LAUNCH_NEW,
                message=f"Launching {app_name.title()}...",
                app_name=app_name,
                window_count=0,
            )

        running_hwnds = self._get_running_windows(app_name, world_snap)
        is_running = len(running_hwnds) > 0
        window_count = len(running_hwnds)
        primary_hwnd = running_hwnds[0] if running_hwnds else None

        if not is_running:
            logger.debug(f"ExecutionPolicy: '{app_name}' not running → LAUNCH_NEW")
            return PolicyDecision(
                action=PolicyAction.LAUNCH_NEW,
                message=f"Launching {app_name.title()}...",
                app_name=app_name,
                window_count=0,
            )

        from .autonomy_mode import AutonomyLevel

        autonomy_level = self.get_autonomy_level()

        # If autonomy level permits automatic reuse (ASSISTED or AUTONOMOUS), reuse existing window
        if autonomy_level != AutonomyLevel.ASK and primary_hwnd:
            logger.info(
                f"ExecutionPolicy: '{app_name}' running ({window_count} windows) under "
                f"{autonomy_level.value.upper()} autonomy → REUSE_EXISTING [hwnd={hex(primary_hwnd)}]"
            )
            return PolicyDecision(
                action=PolicyAction.REUSE_EXISTING,
                message=f"{app_name.title()} is already open — activating existing window.",
                app_name=app_name,
                window_count=window_count,
                hwnd=primary_hwnd,
            )

        # App is already running in ASK mode — ask user
        win_word = "window" if window_count == 1 else "windows"
        msg = (
            f"{app_name.title()} is already open ({window_count} {win_word}). "
            f"Open another instance? (yes / no)"
        )
        key = self._make_key(app_name)
        self._pending[key] = PendingConfirmation(key=key, app_name=app_name, goal=goal)

        logger.info(
            f"ExecutionPolicy: '{app_name}' running ({window_count} {win_word}) "
            f"→ ASK_USER [key={key[:8]}]"
        )
        return PolicyDecision(
            action=PolicyAction.ASK_USER,
            message=msg,
            app_name=app_name,
            window_count=window_count,
            confirmation_key=key,
            hwnd=primary_hwnd,
        )

    def resolve_confirmation(self, user_answer: str) -> PolicyDecision | None:
        """
        Called when the user replies yes/no to a pending open-app confirmation.
        Returns a resolved PolicyDecision if one was pending, else None.
        """
        # Expire stale entries
        stale = [k for k, c in self._pending.items() if c.is_expired()]
        for k in stale:
            del self._pending[k]

        if not self._pending:
            return None

        # Pick most recent pending confirmation
        _, conf = max(self._pending.items(), key=lambda x: x[1].created_at)
        del self._pending[conf.key]

        answer = user_answer.strip().lower()
        if answer in [
            "yes",
            "y",
            "yeah",
            "yep",
            "sure",
            "ok",
            "okay",
            "open",
            "another",
        ]:
            logger.info(
                f"ExecutionPolicy: YES → CONFIRMED_LAUNCH for '{conf.app_name}'"
            )
            return PolicyDecision(
                action=PolicyAction.CONFIRMED_LAUNCH,
                message=f"Opening new {conf.app_name.title()} instance...",
                app_name=conf.app_name,
                window_count=0,
            )
        else:
            # "no" — bring existing to front
            running_hwnds = self._get_running_windows(conf.app_name, None)
            hwnd = running_hwnds[0] if running_hwnds else None
            logger.info(f"ExecutionPolicy: NO → REUSE_EXISTING for '{conf.app_name}'")
            return PolicyDecision(
                action=PolicyAction.REUSE_EXISTING,
                message=f"Bringing existing {conf.app_name.title()} window to front.",
                app_name=conf.app_name,
                window_count=len(running_hwnds),
                hwnd=hwnd,
            )

    def has_pending_confirmation(self) -> bool:
        """Returns True if any non-expired confirmation is pending."""
        return any(not c.is_expired() for c in self._pending.values())

    def get_pending_app_name(self) -> str | None:
        """Returns app_name of the most recent non-expired pending confirmation."""
        valid = [(k, c) for k, c in self._pending.items() if not c.is_expired()]
        if not valid:
            return None
        _, conf = max(valid, key=lambda x: x[1].created_at)
        return conf.app_name

    def clear_all(self) -> None:
        """Clear all pending confirmations."""
        self._pending.clear()

    # ── Private helpers ─────────────────────────────────────────────────────

    def _make_key(self, app_name: str) -> str:
        return hashlib.md5(app_name.lower().encode()).hexdigest()[:16]

    def _get_running_windows(self, app_name: str, world_snap: Any | None) -> list[int]:
        """
        Real OS enumeration via EnumWindows + psutil.
        Returns a list of top-level HWNDs matching this application (may be empty).
        """
        try:
            import psutil
            import win32con
            import win32gui
            import win32process

            app_lower = app_name.lower()
            matches: list[int] = []

            def _enum(hwnd: int, _: Any) -> bool:
                if not win32gui.IsWindowVisible(hwnd):
                    return True

                # Must be a top-level window (no owner or WS_EX_APPWINDOW)
                owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER)
                ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                if owner != 0 and not (ex_style & win32con.WS_EX_APPWINDOW):
                    return True

                # Exclude tool windows without WS_EX_APPWINDOW
                if (ex_style & win32con.WS_EX_TOOLWINDOW) and not (
                    ex_style & win32con.WS_EX_APPWINDOW
                ):
                    return True

                raw_title = win32gui.GetWindowText(hwnd)
                title = raw_title.lower().strip()

                # Ignore known OS helper/IME windows
                if title in [
                    "msctfime ui",
                    "default ime",
                    "cicerouiwndframe",
                    "program manager",
                ]:
                    return True

                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    proc_name = (psutil.Process(pid).name() or "").lower()
                    import re

                    proc_base = re.sub(r"\.exe$", "", proc_name)
                    proc_base = re.sub(r"app$", "", proc_base)
                except Exception:
                    proc_name = ""
                    proc_base = ""

                # Target matching logic: either title matches app_name or process matches AND window has non-empty title
                name_match = (
                    app_lower in proc_base
                    or app_lower in proc_name
                    or app_lower in title
                )
                if name_match:
                    # Require non-empty title to prevent headless/helper HWND duplication
                    if title:
                        matches.append(hwnd)
                return True

            win32gui.EnumWindows(_enum, None)
            return matches

        except ImportError:
            # Fallback: psutil process list
            try:
                import psutil

                app_lower = app_name.lower()
                procs = [
                    p
                    for p in psutil.process_iter(["pid", "name"])
                    if app_lower in (p.info.get("name") or "").lower()
                ]
                return [p.pid for p in procs]
            except Exception:
                return []
        except Exception as exc:
            logger.debug(
                f"ExecutionPolicy._get_running_windows({app_name}) error: {exc}"
            )
            return []
