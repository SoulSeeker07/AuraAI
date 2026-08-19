"""
Conversational Pronoun & World State Reference Resolver
Location: src/core/orchestration/reference_resolver.py

Resolves ambiguous pronouns ('it', 'that', 'this', 'that window', 'the app', 'the browser')
against active WorldSnapshot, WorldTimeline, and ResourceOwnershipTracker context before planning.

Example:
    "Open Notepad" -> Notepad opened
    "Minimize it"  -> ReferenceResolver substitutes 'it' -> 'Notepad' -> "Minimize Notepad"
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .ownership_tracker import ResourceOwnershipTracker
from .world_timeline import WorldTimeline

logger = logging.getLogger(__name__)


class ReferenceResolver:
    """
    Resolves ambiguous conversational references to concrete OS/Browser resources.
    """

    PRONOUN_PATTERNS = [
        r"\b(minimize|close|restore|focus|maximize|activate|hide|show|switch to|open|launch)\s+(it|that|this|that window|the window|the app|the application|the tab|the browser|that tab|that app)\b",
        r"\b(close|minimize|restore|focus)\s+the\s+(last\s+opened|last\s+active|last\s+created)\s+(app|window|tab|file|resource)\b",
        r"^as of (today|now|yesterday|tomorrow)[?]?$",
        r"^(what about|and) (today|now|yesterday|tomorrow)[?]?$",
        r"^how about (today|now|yesterday|tomorrow)[?]?$",
    ]

    @classmethod
    def resolve_references(
        cls, goal_text: str, context: dict[str, Any] | None = None
    ) -> tuple[str, dict[str, Any]]:
        """
        Resolve ambiguous pronouns in goal_text using:
        1. OS-reported focused window (win32gui.GetForegroundWindow)  ← highest confidence
        2. WorldTimeline most-recent desktop event
        3. Aura-owned resources (ResourceOwnershipTracker)
        4. shared_context world_state.focused_window_title

        Returns:
            tuple of (resolved_goal_text, resolution_metadata)
        """
        goal_lower = goal_text.lower().strip()
        has_reference = False

        for pattern in cls.PRONOUN_PATTERNS:
            if re.search(pattern, goal_lower, flags=re.IGNORECASE):
                has_reference = True
                break

        if not has_reference:
            return goal_text, {"resolved": False, "target": None}

        target_name: str | None = None
        target_source: str = "unknown"

        HOST_BLACK_LIST = [
            "code",
            "vscode",
            "visual studio code",
            "windowsterminal",
            "powershell",
            "cmd",
            "python",
            "pythonw",
            "antigravity",
            "electron",
            "cursor",
            "explorer",
            "taskbar",
            "searchhost",
            "unknown",
            "",
        ]

        # ── Priority 1: Conversational Fragments (e.g. "as of today?", "what about tomorrow?") ──
        fragment_patterns = [
            r"^as of (today|now|yesterday|tomorrow)[?]?$",
            r"^(what about|and) (today|now|yesterday|tomorrow)[?]?$",
            r"^how about (today|now|yesterday|tomorrow)[?]?$",
        ]
        is_fragment = any(re.match(p, goal_lower) for p in fragment_patterns)
        if is_fragment:
            try:
                from Memory import Memory as AuraMemory
                mem = AuraMemory()
                recent = mem.recent_messages(limit=5)
                last_user_msg = None
                for msg in reversed(recent):
                    if msg.get("role") == "user":
                        last_user_msg = msg.get("content", "")
                        break
                if last_user_msg:
                    clean_last = re.sub(r"\b(current|latest|now)\b", "", last_user_msg, flags=re.IGNORECASE).strip()
                    clean_fragment = goal_lower.rstrip("?")
                    resolved_text = f"{clean_last} {clean_fragment}".strip()
                    resolved_text = re.sub(r"\s+", " ", resolved_text)
                    logger.info(
                        f"ReferenceResolver: Fragment '{goal_text}' resolved using previous context -> '{resolved_text}'"
                    )
                    return resolved_text, {
                        "resolved": True,
                        "target": clean_last,
                        "source": "conversational_memory",
                        "original_goal": goal_text,
                    }
            except Exception as exc:
                logger.debug(f"ReferenceResolver: Fragment resolution failed: {exc}")

        # ── Priority 2: Aura-owned resources & Session context (Last referenced object) ──
        try:
            aura_resources = (
                ResourceOwnershipTracker.get_instance().get_aura_resources()
            )
            if aura_resources:
                last_res = aura_resources[-1]
                t_candidate = (
                    last_res.details.get("app_name")
                    or last_res.details.get("site")
                    or last_res.resource_id
                )
                if t_candidate and t_candidate.lower() not in HOST_BLACK_LIST:
                    target_name = t_candidate
                    target_source = "ownership_tracker:last_referenced_object"
        except Exception as exc:
            logger.debug(f"ReferenceResolver: ownership probe failed: {exc}")

        # ── Priority 3: WorldTimeline most-recent resource event ───────────
        if not target_name:
            try:
                timeline = WorldTimeline.get_instance().get_recent_events(minutes=30)
                for evt in reversed(timeline):
                    if any(
                        w in evt.event_type
                        for w in [
                            "process",
                            "tab",
                            "window",
                            "app",
                            "open",
                            "launch",
                            "activate",
                            "minimize",
                        ]
                    ):
                        res_id = (evt.resource_id or "").lower()
                        if (
                            res_id
                            and res_id not in HOST_BLACK_LIST
                            and res_id not in ["session", "hi", "it"]
                        ):
                            target_name = evt.resource_id
                            target_source = f"timeline:{evt.event_type}"
                            break
                        desc = evt.description.lower()
                        m = re.search(r"['\"]([^'\"]+)['\"]", desc)
                        if m:
                            candidate = m.group(1).strip()
                            if (
                                candidate
                                and candidate.lower() not in HOST_BLACK_LIST
                                and candidate.lower()
                                not in ["everything you opened", "session", "hi", "it"]
                            ):
                                target_name = candidate
                                target_source = f"timeline_desc:{evt.event_type}"
                                break
            except Exception as exc:
                logger.debug(f"ReferenceResolver: timeline probe failed: {exc}")

        # ── Priority 3: Focused window from live Windows OS (excluding host IDE/terminals) ─
        if not target_name:
            try:
                import psutil
                import win32gui
                import win32process

                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    title = win32gui.GetWindowText(hwnd)
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    proc_name = ""
                    try:
                        proc_name = (
                            psutil.Process(pid)
                            .name()
                            .replace(".exe", "")
                            .replace("App", "")
                        )
                    except Exception:
                        pass

                    candidate = proc_name or title.split("-")[0].strip()
                    if candidate and candidate.lower() not in HOST_BLACK_LIST:
                        target_name = candidate
                        target_source = f"focused_window:hwnd={hwnd},pid={pid}"
                        logger.info(
                            f"ReferenceResolver: focused window → '{target_name}' (pid={pid})"
                        )
            except Exception as exc:
                logger.debug(f"ReferenceResolver: focused window probe failed: {exc}")

        # ── Priority 4: Context world_state ────────────────────────────────
        if not target_name and context:
            world_state = context.get("world_state", {})
            focused = world_state.get("focused_window_title", "")
            if focused:
                target_name = focused.split("-")[0].strip()
                target_source = "world_state_context"

        if target_name:
            resolved_text = re.sub(
                r"\b(it|that|this|that window|the window|the app|the application|the tab|that tab|that app)\b",
                target_name,
                goal_text,
                flags=re.IGNORECASE,
            )
            logger.info(
                f"ReferenceResolver: '{goal_text}' → '{resolved_text}' "
                f"(target='{target_name}', source={target_source})"
            )
            return resolved_text, {
                "resolved": True,
                "target": target_name,
                "source": target_source,
                "original_goal": goal_text,
            }

        return goal_text, {"resolved": False, "target": None}
