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
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


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
    Singleton that evaluates every desktop action request and decides
    REUSE_EXISTING | LAUNCH_NEW | ASK_USER | CONFIRMED_LAUNCH | FAIL.

    Holds pending confirmations across turns.
    """

    _instance: "ExecutionPolicy | None" = None

    def __init__(self) -> None:
        self._pending: dict[str, PendingConfirmation] = {}

    @classmethod
    def get_instance(cls) -> "ExecutionPolicy":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # ── Public API ──────────────────────────────────────────────────────────

    def evaluate(
        self,
        goal: str,
        app_name: str,
        world_snap: Any | None = None,
    ) -> PolicyDecision:
        """
        Evaluate an app_open intent against live OS world state.

        Priority:
        1. App NOT running → LAUNCH_NEW
        2. App IS running  → count real EnumWindows HWNDs → ASK_USER
        """
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

        # App is already running — ask user
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
        if answer in ["yes", "y", "yeah", "yep", "sure", "ok", "okay", "open", "another"]:
            logger.info(f"ExecutionPolicy: YES → CONFIRMED_LAUNCH for '{conf.app_name}'")
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
        Returns a list of HWNDs matching this application (may be empty).
        """
        try:
            import win32gui
            import win32process
            import psutil

            app_lower = app_name.lower()
            matches: list[int] = []

            def _enum(hwnd: int, _: Any) -> bool:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                title = win32gui.GetWindowText(hwnd).lower()
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    proc_name = (psutil.Process(pid).name() or "").lower()
                    proc_base = proc_name.replace(".exe", "").replace("app", "")
                except Exception:
                    proc_name = ""
                    proc_base = ""
                if app_lower in title or app_lower in proc_base or app_lower in proc_name:
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
                    p for p in psutil.process_iter(["pid", "name"])
                    if app_lower in (p.info.get("name") or "").lower()
                ]
                return [p.pid for p in procs]
            except Exception:
                return []
        except Exception as exc:
            logger.debug(f"ExecutionPolicy._get_running_windows({app_name}) error: {exc}")
            return []
