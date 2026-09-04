"""
Ambient Context Builder
=======================
Fast assembler for real-time ambient environment context:
- Focused active window title
- User profile & preferences from Memory.db
- System telemetry (battery, RAM, CPU)
- Sanitized clipboard snippet
- Local time and date
"""

from __future__ import annotations

import datetime
import logging
import re
import time
from typing import Any

logger = logging.getLogger(__name__)


class AmbientContextBuilder:
    """Builds a rich, real-time ambient context string to ground LLM reasoning."""

    @classmethod
    def build_ambient_context(cls, aura_core: Any = None, query: str = "") -> str:
        """
        Gathers live system state quickly (< 50ms) without blocking.
        """
        now = datetime.datetime.now().strftime("%A, %B %d, %Y - %I:%M %p")
        context_parts = [f"📅 **Current System Time**: {now}"]

        # 1. Active Focused Window
        active_window = cls._get_active_window()
        if active_window:
            context_parts.append(f"🖥️ **Active Focused Window**: \"{active_window}\"")

        # 2. System Hardware / Battery
        sys_status = cls._get_quick_sys_info()
        if sys_status:
            context_parts.append(f"⚡ **Hardware State**: {sys_status}")

        # 3. User Profile & Preferences from Memory (Hybrid Semantic Recall)
        if aura_core and hasattr(aura_core, "memory") and aura_core.memory:
            if hasattr(aura_core, "embedding_warmup") and aura_core.embedding_warmup:
                aura_core.embedding_warmup.ensure_ready_sync(timeout=0.05)
            user_facts = cls._get_memory_summary(aura_core.memory, query=query)
            if user_facts:
                context_parts.append(f"👤 **Relevant User Facts & Preferences**:\n{user_facts}")

        # 4. Clipboard Preview (Sanitized)
        clip_preview = cls._get_clipboard_preview()
        if clip_preview:
            context_parts.append(f"📋 **Clipboard Preview**: \"{clip_preview}\"")

        # 5. Speculative Workspace Context
        if aura_core and getattr(aura_core, "speculative_indexer", None):
            try:
                ws_ctx = aura_core.speculative_indexer.get_prewarmed_context(wait_if_pending=False)
                if ws_ctx:
                    snippet = ws_ctx.to_prompt_snippet()
                    if snippet:
                        context_parts.append(f"📁 **Workspace Context**:\n{snippet}")
            except Exception as ws_err:
                logger.debug(f"[AmbientContext] Speculative indexer note: {ws_err}")

        return "\n".join(context_parts)


    @staticmethod
    def _get_active_window() -> str:
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                title = win32gui.GetWindowText(hwnd)
                return title.strip() if title else "Desktop"
        except Exception:
            pass
        return ""

    @staticmethod
    def _get_quick_sys_info() -> str:
        try:
            import psutil
            battery = psutil.sensors_battery()
            battery_str = f"{battery.percent}% ({'Plugged In' if battery.power_plugged else 'On Battery'})" if battery else "AC Power"
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent
            return f"CPU: {cpu}% | RAM: {mem}% | Battery: {battery_str}"
        except Exception:
            return ""

    @staticmethod
    def _get_memory_summary(memory: Any, query: str = "") -> str:
        try:
            if query and hasattr(memory, "get_relevant_facts"):
                facts = memory.get_relevant_facts(query, limit=10)
            elif hasattr(memory, "all_facts"):
                facts = memory.all_facts()
            elif hasattr(memory, "facts"):
                facts = memory.facts()
            else:
                facts = []

            if not facts:
                return ""
            lines = []
            for f in facts[:10]:
                lines.append(f"- [{f.category}] {f.key}: {f.value}")
            return "\n".join(lines)
        except Exception:
            return ""

    _clipboard_cache_text: str = ""
    _clipboard_cache_time: float = 0.0
    _CLIPBOARD_TTL: float = 2.0  # seconds

    @classmethod
    def _get_clipboard_preview(cls) -> str:
        now = time.time()
        if (now - cls._clipboard_cache_time) < cls._CLIPBOARD_TTL:
            return cls._clipboard_cache_text

        text = ""
        try:
            import win32clipboard
            import win32con

            win32clipboard.OpenClipboard()
            try:
                text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
        except Exception as win_err:
            logger.debug(f"[AmbientContext] win32clipboard access note: {win_err}")
            # Quick fallback to pure-ctypes user32 via pyperclip without spawning subprocesses
            try:
                import pyperclip
                text = pyperclip.paste()
            except Exception as pyp_err:
                logger.debug(f"[AmbientContext] pyperclip fallback note: {pyp_err}")

        if not text or not isinstance(text, str):
            cls._clipboard_cache_text = ""
            cls._clipboard_cache_time = now
            return ""

        cleaned = text.strip()
        # Best-effort client-side heuristics for common credentials / payment patterns
        cleaned = re.sub(r"(?:api[_-]?key|secret|token|password)[\s:=]+['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?", "[REDACTED_SECRET]", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b(?:\d[ -]*?){13,16}\b", "[REDACTED_CARD]", cleaned)

        if len(cleaned) > 120:
            cleaned = cleaned[:117] + "..."
        result = cleaned.replace("\n", " ")

        cls._clipboard_cache_text = result
        cls._clipboard_cache_time = now
        return result
