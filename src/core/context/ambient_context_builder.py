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

            # 3b. Negative Constraints / Anti-Patterns from Procedural Failure Ledger
            ledger = getattr(aura_core.memory, "failure_ledger", None)
            if not ledger and getattr(aura_core.memory, "cognitive", None):
                ledger = getattr(aura_core.memory.cognitive, "failure_ledger", None)
            if ledger:
                try:
                    anti_pat_block = ledger.format_anti_patterns_prompt(limit=3)
                    if isinstance(anti_pat_block, str) and anti_pat_block.strip():
                        context_parts.append(anti_pat_block)
                except Exception as ap_err:
                    logger.debug(f"[AmbientContextBuilder] Anti-pattern prompt error: {ap_err}")

        # 4. Clipboard Preview (Sequence-gated: only fresh clipboard modifications during active session)
        clip_preview = cls._get_fresh_clipboard_preview(query=query)
        if clip_preview:
            context_parts.append(
                f'📋 **Clipboard Buffer** (Passive background context only — do NOT proactively diagnose, critique, or mention this unless the user explicitly asks about it): "{clip_preview}"'
            )

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
            lines: list[str] = []
            has_cognitive = hasattr(memory, "cognitive") and memory.cognitive is not None
            cognitive_failed = False

            # Check if this is an explicit identity / profile / memory query
            q_low = (query or "").lower().strip()
            is_identity_query = any(
                k in q_low
                for k in (
                    "about me", "who am i", "my profile", "know about me", "tell me about myself",
                    "what do you know", "what you know", "in detailed", "detailed", "my facts",
                    "my preferences", "remember about me", "stored about me", "my info", "who i am"
                )
            )

            # 1. Cognitive Memory 2.0 via MemoryRetrievalGate (Gated Recall)
            if query and has_cognitive:
                try:
                    gate_factory = getattr(memory.cognitive, "get_retrieval_gate", None)
                    if callable(gate_factory):
                        retrieval_gate = gate_factory()
                        mem_ctx = retrieval_gate.get_context(query)
                        if getattr(mem_ctx, "skip_reason", None) == "retrieval_error":
                            cognitive_failed = True
                        else:
                            prompt_frag = mem_ctx.to_prompt_fragment()
                            if prompt_frag:
                                lines.append(prompt_frag)
                    else:
                        cognitive_failed = True
                except Exception as c_err:
                    logger.debug(f"[AmbientContextBuilder] Cognitive memory recall error: {c_err}")
                    cognitive_failed = True

            # 2. Structured Profile Facts:
            # If the query asks about the user's identity/facts, or if cognitive memory had nothing to surface:
            # Always ensure the user's personal facts, preferences, skills, and projects are surfaced!
            if (not lines and (not has_cognitive or not query or cognitive_failed or is_identity_query)) or is_identity_query:
                user_categories = {"person", "profile", "preference", "skills", "work", "projects", "important"}
                if hasattr(memory, "all_facts"):
                    all_f = memory.all_facts()
                elif hasattr(memory, "facts"):
                    all_f = memory.facts()
                else:
                    all_f = []

                if is_identity_query:
                    # For identity inquiries, surface all user-related profile facts
                    user_facts = [f for f in all_f if getattr(f, "category", "") in user_categories]
                    for f in user_facts:
                        f_line = f"- [{f.category}] {f.key}: {f.value}"
                        if f_line not in lines:
                            lines.append(f_line)
                elif not lines:
                    for f in all_f[:10]:
                        lines.append(f"- [{f.category}] {f.key}: {f.value}")

            return "\n".join(lines)
        except Exception:
            return ""

    _clipboard_cache_text: str = ""
    _clipboard_cache_time: float = 0.0
    _CLIPBOARD_TTL: float = 2.0  # seconds
    _baseline_clipboard_seq: int | None = None

    @classmethod
    def _get_current_clipboard_sequence(cls) -> int | None:
        try:
            import win32clipboard
            return int(win32clipboard.GetClipboardSequenceNumber())
        except Exception:
            return None

    @classmethod
    def reset_clipboard_baseline(cls, force_seq: int | None = None) -> None:
        """Reset or initialize the session baseline clipboard sequence number."""
        cls._baseline_clipboard_seq = force_seq if force_seq is not None else cls._get_current_clipboard_sequence()

    @classmethod
    def _get_fresh_clipboard_preview(cls, query: str = "") -> str:
        """
        Retrieves clipboard preview ONLY if the clipboard was modified during this active session
        (tracked via Windows GetClipboardSequenceNumber) or if the query explicitly asks about clipboard.
        """
        curr_seq = cls._get_current_clipboard_sequence()

        # Initialize baseline on first access if not yet set
        if cls._baseline_clipboard_seq is None:
            cls._baseline_clipboard_seq = curr_seq

        # Explicit clipboard inquiries always bypass freshness gating
        q_lower = (query or "").lower()
        is_explicit_clipboard_query = any(k in q_lower for k in ["clipboard", "copied", "paste", "pasted"])

        # If sequence number is unchanged from session baseline, omit stale clipboard
        if curr_seq is not None and cls._baseline_clipboard_seq is not None:
            if curr_seq == cls._baseline_clipboard_seq and not is_explicit_clipboard_query:
                return ""

        # Advance baseline to current sequence number so each modification is only delivered as fresh once
        if curr_seq is not None and not is_explicit_clipboard_query:
            cls._baseline_clipboard_seq = curr_seq

        return cls._get_clipboard_preview()

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
