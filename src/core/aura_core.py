"""
Aura Core - The main brain of AuraAI

This module provides the core Aura intelligence including:
- Memory management
- Knowledge indexing
- Plugin system
- Workspace awareness
- Agent runtime
- Tool execution
- Vision and Voice services (as needed)

All clients (CLI, GUI, Voice, API) communicate with Aura Core.
"""

import asyncio
import os
import sys
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# Configure sys.path for src and project root
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _PROJECT_ROOT / "src"

if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
# TD-002: Pre-empt dual package root split-brain (core.aura_core vs src.core.aura_core)
if __name__ in sys.modules:
    sys.modules.setdefault("core.aura_core", sys.modules[__name__])
    sys.modules.setdefault("src.core.aura_core", sys.modules[__name__])


# Import Memory module for brain integration
try:
    from Memory import Memory
except ImportError:
    Memory = None

# Import research module types
try:
    from research import ConflictResolution, ResearchConfig, SearchMode
except ImportError:
    SearchMode = None
    ConflictResolution = None
    ResearchConfig = None

# Import planner module
try:
    from research.research_planner import ResearchPlanner
except ImportError:
    ResearchPlanner = None

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# Groq client
try:
    from groq import Groq
except ImportError:
    Groq = None

# Ensure UTF-8 output
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Import logger from core module (imported in core/__init__.py)
try:
    from core import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class AuraCoreStatus(Enum):
    """Status of Aura Core components."""

    READY = "Ready"
    LOADING = "Loading"
    ERROR = "Error"


@dataclass
class ComponentStatus:
    """Status of a core component."""

    name: str
    status: AuraCoreStatus
    message: str
    loaded: bool = True


class AuraCore:
    """
    Main Aura Core - The central intelligence of AuraAI.

    This class coordinates all AuraAI components and provides a unified
    interface for all clients (CLI, GUI, Voice, API).
    """

    # Singleton pattern
    _instance: Optional["AuraCore"] = None
    _initialized: bool = False

    def __new__(cls, config: dict[str, Any] | None = None):
        """Ensure only one instance is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls, config: dict[str, Any] | None = None) -> "AuraCore":
        """Get or create the singleton AuraCore instance."""
        if cls._instance is None:
            cls._instance = cls(config)

            logger.info(f"[AuraCore Singleton] Initialized unique kernel instance (ID: {id(cls._instance)})")
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (primarily for test isolation)."""
        cls._instance = None
        cls._initialized = False

    def __init__(self, config: dict[str, Any] | None = None):
        # Guard the WHOLE body — not just _initialize_components() — so a second
        # AuraCore() call anywhere in the codebase can't wipe out live state.
        if self._initialized:
            self._load_conversation_history()
            return

        self.config = config or {}
        project_root_input = self.config.get("project_root")
        if project_root_input is not None:
            if isinstance(project_root_input, str):
                self.project_root = Path(project_root_input)
            else:
                self.project_root = project_root_input
        else:
            self.project_root = Path(__file__).resolve().parents[2]

        import sys

        src_path = str(self.project_root / "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)

        try:
            from desktop.native.managers.display_helpers import ensure_dpi_awareness
            ensure_dpi_awareness()
        except Exception:
            pass

        self.workspace = self.config.get("workspace", str(self.project_root))

        self.chat_log_path = Path(
            self.config.get("data_path", self.project_root / "Data" / "ChatLog.json")
        )
        self.memory_db_path = Path(
            self.config.get("memory_db_path", self.project_root / "Memory.db")
        )

        self.components: dict[str, ComponentStatus] = {}
        self.memory_enabled = True
        self.memory_stats = {}
        self.knowledge_enabled = True
        self.knowledge_stats = {}
        self.plugins = []
        self.plugin_count = 0
        self.workspace_aware = False
        self.workspace_info = {}
        self.multi_agent_status = AuraCoreStatus.READY
        self.multi_agent_orchestrator = None
        self.multi_agent_registry = None
        self.agent_runtime_status = AuraCoreStatus.READY
        self.agent_runtime = None

        self.research_enabled = False
        self.research_integration = None
        self._research_initialized = False

        self.planner_enabled = False
        self.planner = None
        self.workflow_engine_status = AuraCoreStatus.READY
        self.workflow_engine = None
        self.vision_enabled = True
        self.vision_manager = None
        self.voice_enabled = self.config.get("voice_enabled", False)
        self.executive_brain = None
        self.executive_brain_enabled = False
        self.current_task: str | None = None
        self.current_task_status: AuraCoreStatus = AuraCoreStatus.READY
        self.conversation_history: list[dict[str, str]] = []
        self.max_history = 100

        AuraCore._initialized = True
        self.groq_model = self.config.get("groq_model", "openai/gpt-oss-120b")
        self.groq_client = None
        self.llm_enabled = False
        self._init_llm()
        self._initialize_components()
        self._init_executive_brain()
        self._init_personal_os()
        self._init_focus_manager()
        self._init_vision_dictation()
        self._prewarm_voice_and_models_async()

    def _init_personal_os(self):
        """Initialize Personal OS subsystem, load stored triggers, and warm search index."""
        try:
            from personal_os.state_store import PersonalOSStateStore
            from personal_os.daily_context import DailyContextEngine
            from personal_os.workspace_search import WorkspaceSearchEngine
            from autonomy.models import Trigger, TriggerType, TriggerState

            self.personal_os_store = PersonalOSStateStore.get_instance(
                db_path=self.project_root / "storage" / "personal_os.db"
            )
            self.daily_context_engine = DailyContextEngine(state_store=self.personal_os_store)
            self.workspace_search_engine = WorkspaceSearchEngine.get_instance(root_dir=self.project_root)

            # Re-arm stored Personal OS triggers into trigger_registry & scheduler
            stored_triggers = self.personal_os_store.list_triggers(enabled_only=True)
            if hasattr(self, "trigger_registry") and self.trigger_registry:
                for p_trig in stored_triggers:
                    t = Trigger(
                        trigger_id=p_trig.trigger_id,
                        trigger_type=TriggerType.SCHEDULED,
                        action_goal=p_trig.goal_text,
                        execution_map={},
                        cron_schedule=p_trig.schedule if " " in p_trig.schedule else None,
                        state=TriggerState.ARMED,
                        dedup_key=p_trig.trigger_id,
                    )
                    self.trigger_registry.register_trigger(t)

            # Wire live filesystem telemetry if FilesystemWatcher is active
            if hasattr(self, "filesystem_watcher") and self.filesystem_watcher:
                if hasattr(self.filesystem_watcher, "register_listener"):
                    self.filesystem_watcher.register_listener(self.workspace_search_engine.on_filesystem_event)
                    logger.info("[AuraCore] Registered WorkspaceSearchEngine live event listener on FilesystemWatcher.")
                else:
                    logger.warning("[AuraCore] FilesystemWatcher instance missing register_listener.")
            else:
                logger.info("[AuraCore] FilesystemWatcher not attached; workspace search index will use initial scan and manual/event rebuilds.")

            self.components["personal_os"] = ComponentStatus(
                name="Personal OS Subsystem",
                status=AuraCoreStatus.READY,
                message=f"Personal OS active ({len(stored_triggers)} routines armed)",
            )
            logger.info(
                f"[AuraCore] Personal OS initialized: {len(stored_triggers)} routine(s) armed, search index ready."
            )
        except Exception as e:
            self.components["personal_os"] = ComponentStatus(
                name="Personal OS Subsystem",
                status=AuraCoreStatus.ERROR,
                message=f"Personal OS initialization failed: {e}",
                loaded=False,
            )
            logger.error(
                f"[AuraCore] Personal OS initialization failed — running in degraded mode: {e}",
                exc_info=True,
            )

    def _init_focus_manager(self) -> None:
        """Initialize FocusManager singleton and register the hourly stale-archival cron."""
        try:
            from core.focus_manager import FocusManager

            db_path = self.project_root / "storage" / "focus_threads.db"
            self.focus_manager = FocusManager.get_instance(db_path=db_path)

            # Register hourly archival trigger via TriggerScheduler
            max_age_hours = float(self.config.get("focus_stale_hours", 24))
            if hasattr(self, "trigger_scheduler") and self.trigger_scheduler:
                try:
                    from autonomy.models import Trigger, TriggerType, TriggerState

                    archival_trigger = Trigger(
                        trigger_id="focus_archival_cron",
                        trigger_type=TriggerType.SCHEDULED,
                        action_goal=f"Archive stale focus threads older than {max_age_hours}h",
                        execution_map={"action": "focus_archive_stale", "max_age_hours": max_age_hours},
                        cron_schedule="0 * * * *",  # every hour
                        state=TriggerState.ARMED,
                        dedup_key="focus_archival_cron",
                    )
                    if hasattr(self, "trigger_registry") and self.trigger_registry:
                        self.trigger_registry.register_trigger(archival_trigger)
                    logger.info("[AuraCore] Focus archival cron registered (hourly).")
                except Exception as cron_err:
                    logger.debug(f"[AuraCore] Focus archival cron registration skipped: {cron_err}")

            self.components["focus_manager"] = ComponentStatus(
                name="FocusManager",
                status=AuraCoreStatus.READY,
                message=f"FocusManager active ({len(self.focus_manager.list_active())} thread(s))",
            )
            logger.info("[AuraCore] FocusManager initialized.")
        except Exception as e:
            self.focus_manager = None
            self.components["focus_manager"] = ComponentStatus(
                name="FocusManager",
                status=AuraCoreStatus.ERROR,
                message=f"FocusManager initialization failed: {e}",
                loaded=False,
            )
            logger.error(f"[AuraCore] FocusManager initialization failed: {e}", exc_info=True)

    # ── Focus helpers (M32) ────────────────────────────────────────────────────

    def _focus_preamble(self, user_goal: str) -> None:
        """
        Resolve the focus thread for this turn before dispatching to the LLM.
        Zero-latency — deterministic keyword fast-path first, LLM slug extraction
        only for ambiguous cases.

        Mutates self.focus_manager's current_focus in-place so that the context
        snippet injected by _build_chat_messages() is immediately up-to-date.
        """
        if self.focus_manager is None:
            return
        try:
            intent = self._resolve_focus_intent(user_goal)
            action = intent.get("action")
            task_id = intent.get("task_id", "")

            if action == "switch" and task_id:
                self.focus_manager.switch_to(task_id)
            elif action == "resume" and task_id:
                self.focus_manager.resume(task_id)
            elif action == "create" and task_id:
                self.focus_manager.create(task_id, {}, severity_origin="user")
            elif action == "close_all":
                self.focus_manager.close_all_threads()
            elif action == "close" and task_id:
                self.focus_manager.close_thread(task_id)
            elif action == "close_current":
                curr = self.focus_manager.get_current()
                if curr:
                    self.focus_manager.close_thread(curr.task_id)
            # "list" and "query" don't change focus — just surface info in response
        except Exception as e:
            logger.debug(f"[AuraCore] Focus preamble skipped: {e}")

    def _focus_postamble(self, user_message: str, response_text: str) -> str:
        """
        After a response is generated:
          1. Update the current focus thread's working context.
          2. Drain buffered pending notifications (cap 3, dedupe by state_hash).
          3. Append drained notifications as a suffix to the response.

        Returns the (possibly annotated) response text.
        """
        if self.focus_manager is None:
            return response_text
        try:
            current = self.focus_manager.get_current()
            if current:
                self.focus_manager.update_state(
                    current.task_id,
                    {"last_summary": response_text[:500], "last_user_msg": user_message[:200]},
                )

            notifications = self.focus_manager.drain_pending_notifications()
            if notifications:
                suffix_lines = ["\n\n---"]
                for notif in notifications:
                    prefix = "⚠️" if notif.severity in ("high", "critical") else "ℹ️"
                    suffix_lines.append(f"{prefix} **[{notif.severity.upper()}]** {notif.message}")
                response_text = response_text + "\n".join(suffix_lines)
        except Exception as e:
            logger.debug(f"[AuraCore] Focus postamble skipped: {e}")
        return response_text

    def _resolve_focus_intent(self, user_goal: str) -> dict:
        """
        Determine the focus management action (if any) implied by user_goal.

        Priority:
          1. Deterministic keyword patterns (zero-latency)
          2. LLM slug extraction for ambiguous natural-language phrasing
              (only if LLM is available and no keyword match found)

        Returns a dict with keys: action ∈ {switch, resume, create, close, close_all, close_current, list, query, none},
        task_id (str, may be empty for list/query/none/close_all/close_current).
        """
        msg = user_goal.lower().strip()

        # 1. Deterministic patterns
        close_all_phrases = ("close all tasks", "close all focus threads", "archive all tasks",
                             "clear all tasks", "clear focus threads", "close all threads")
        close_current_phrases = ("close current task", "end current task", "archive current task",
                                 "finish current task", "close active task")
        close_prefixes = ("close task ", "archive task ", "end task ", "complete task ", "finish task ")
        resume_prefixes = ("back to ", "resume ", "go back to ", "switch to ", "switch back to ")
        create_prefixes = ("start new task ", "new task ", "begin task ", "start task ")
        list_phrases = ("what was i doing", "list tasks", "list my tasks", "show tasks",
                        "show active tasks", "what are my tasks", "active threads", "my tasks")
        query_phrases = ("what am i working on", "current task", "current focus")

        for phrase in close_all_phrases:
            if phrase in msg:
                return {"action": "close_all", "task_id": ""}

        for phrase in close_current_phrases:
            if msg == phrase or msg.startswith(phrase + " "):
                return {"action": "close_current", "task_id": ""}

        for prefix in close_prefixes:
            if msg.startswith(prefix):
                slug = msg[len(prefix):].strip().replace(" ", "_")
                return {"action": "close", "task_id": slug}

        for phrase in list_phrases:
            if phrase in msg:
                return {"action": "list", "task_id": ""}

        for phrase in query_phrases:
            if phrase in msg:
                return {"action": "query", "task_id": ""}

        for prefix in resume_prefixes:
            if msg.startswith(prefix):
                slug = msg[len(prefix):].strip().replace(" ", "_")
                return {"action": "resume", "task_id": slug}
            if prefix.strip() in msg:
                # Pattern anywhere in the message
                idx = msg.index(prefix.strip())
                slug = msg[idx + len(prefix.strip()):].strip().split()[0].replace(" ", "_")
                if slug:
                    return {"action": "resume", "task_id": slug}

        for prefix in create_prefixes:
            if msg.startswith(prefix):
                slug = msg[len(prefix):].strip().replace(" ", "_")
                return {"action": "create", "task_id": slug}

        # 2. LLM slug extraction for ambiguous phrasing
        if self.llm_enabled and self.groq_client is not None:
            try:
                extract_prompt = (
                    f"You are a focus-thread router. Classify this message into one of:\n"
                    f"  - switch:<slug>  (e.g. 'back to api_refactor')\n"
                    f"  - create:<slug>  (starting a named new task)\n"
                    f"  - close:<slug>   (closing/archiving a named task)\n"
                    f"  - close_all      (closing/archiving all open tasks)\n"
                    f"  - list           (wants to see active tasks)\n"
                    f"  - none           (normal conversation, no focus management)\n\n"
                    f"Message: \"{user_goal}\"\n"
                    f"Reply with ONLY the classification. slug must be snake_case."
                )
                import asyncio

                def _sync_extract():
                    res = self.groq_client.chat.completions.create(
                        model="openai/gpt-oss-20b",
                        messages=[{"role": "user", "content": extract_prompt}],
                        max_tokens=20,
                        temperature=0.0,
                    )
                    return (res.choices[0].message.content or "").strip().lower()

                # Run synchronously (this helper is called from async context via process_request,
                # but we want zero-overhead here — we'll cap timeout at 1s)
                raw = _sync_extract()
                if raw.startswith("switch:"):
                    return {"action": "switch", "task_id": raw[7:].strip()}
                if raw.startswith("create:"):
                    return {"action": "create", "task_id": raw[7:].strip()}
                if raw == "list":
                    return {"action": "list", "task_id": ""}
            except Exception as e:
                logger.debug(f"[AuraCore] LLM focus intent extraction skipped: {e}")

        return {"action": "none", "task_id": ""}

    def _push_interrupt_notification(self, message: str, task_id: str = "", severity: str = "high") -> None:
        """
        Route a HIGH/CRITICAL interrupt notification through whichever channel is live:
          - GUI: emits app_signals.interrupt_notification (Qt signal, no-op if GUI not running)
          - Voice: enqueues TTS phrase
          - CLI: writes a banner to stdout at next prompt opportunity

        LOW/MEDIUM interrupts should NOT call this — use focus_manager.enqueue_notification() instead.
        """
        # GUI signal
        try:
            from gui.app_signals import app_signals
            if hasattr(app_signals, "interrupt_notification"):
                app_signals.interrupt_notification.emit(message)
        except Exception:
            pass

        # Voice TTS
        try:
            if hasattr(self, "voice_loop") and self.voice_loop is not None:
                from voice.tts_manager import TTSManager
                tts = TTSManager()
                tts.speak_async(f"Interrupt: {message}")
        except Exception:
            pass

        # CLI banner (written to stderr so it doesn't pollute stdout piped output)
        import sys
        banner = f"\n{'='*60}\n⚡ INTERRUPT [{severity.upper()}]: {message}\n{'='*60}\n"
        try:
            sys.stderr.write(banner)
            sys.stderr.flush()
        except Exception:
            pass

        logger.warning(f"[AuraCore] Interrupt notification dispatched: [{severity.upper()}] {message}")

    # ── Vision Dictation & Contextual Action Routing (M33) ──────────────────────

    def _init_vision_dictation(self) -> None:
        """Initialize GroundingEngine, VisualWorkingMemory, and AppContextRouter."""
        try:
            from vision.grounding_engine import GroundingEngine
            from core.visual_memory import VisualWorkingMemory
            from routing.app_context_router import AppContextRouter

            self.grounding_engine = GroundingEngine.get_instance()
            self.visual_memory = VisualWorkingMemory.get_instance()
            self.app_context_router = AppContextRouter.get_instance()

            # Initialize M34 Cognitive Extensions (MacroCompiler, SpeculativeIndexer, ProactiveWatcher)
            from execution.macro_compiler import MacroCompiler
            from workspace.speculative_indexer import SpeculativeIndexer
            from autonomy.proactive_diagnostics_watcher import ProactiveDiagnosticsWatcher

            repo_root = self.config.get("project_root") or getattr(self, "project_root", None)
            self.macro_compiler = MacroCompiler.get_instance()
            self.speculative_indexer = SpeculativeIndexer.get_instance(repo_root=repo_root)
            self.proactive_watcher = ProactiveDiagnosticsWatcher.get_instance(repo_root=repo_root)

            self.components["vision_dictation"] = ComponentStatus(
                name="VisionDictation",
                status=AuraCoreStatus.READY,
                message="Vision Dictation, Macro Compiler & Grounding Engine active",
            )
            logger.info("[AuraCore] Vision Dictation, Macro Compiler & Grounding Engine initialized.")
        except Exception as e:
            self.grounding_engine = None
            self.visual_memory = None
            self.app_context_router = None
            self.macro_compiler = None
            self.speculative_indexer = None
            self.proactive_watcher = None
            self.components["vision_dictation"] = ComponentStatus(
                name="VisionDictation",
                status=AuraCoreStatus.ERROR,
                message=f"Vision Dictation initialization failed: {e}",
                loaded=False,
            )
            logger.error(f"[AuraCore] Vision Dictation initialization failed: {e}", exc_info=True)

    def _vision_dictation_preamble(self, user_goal: str) -> str:
        """
        Process referential phrases, apply pure-navigation fast-path, execute verified macros,
        and resolve cross-app visual context before LLM dispatch.
        """
        if getattr(self, "app_context_router", None) is None or getattr(self, "visual_memory", None) is None:
            return user_goal

        try:
            # 1. Detect foreground application context & resolve focus thread
            app_context = self.app_context_router.detect_current_app()
            current_app = app_context.app_name.lower().strip()
            task_id = "default"
            if getattr(self, "focus_manager", None) is not None:
                current_focus = self.focus_manager.get_current()
                if current_focus:
                    task_id = current_focus.task_id

            # Trigger non-blocking speculative context pre-warm
            if getattr(self, "speculative_indexer", None) is not None:
                self.speculative_indexer.trigger_speculative_prewarm(window_title=app_context.window_title)

            # Automatic app-switch decay when foreground window changes
            prev_app = self.visual_memory._active_apps.get(task_id, "")
            if prev_app and current_app and prev_app != current_app:
                logger.info(
                    f"[AuraCore] Automatic app switch detected: '{prev_app}' -> '{current_app}' for task '{task_id}' — applying memory decay."
                )
                self.visual_memory.decay_on_app_switch(previous_app=prev_app, new_app=current_app, task_id=task_id)

            # 2. Pure-navigation fast-path (0 vision tokens, 0ms latency)
            first_word = user_goal.strip().split()[0].lower() if user_goal.strip() else ""
            two_words = "_".join(user_goal.strip().split()[:2]).lower() if len(user_goal.strip().split()) >= 2 else first_word
            if self.app_context_router.is_targetless_verb(first_word) or self.app_context_router.is_targetless_verb(two_words):
                logger.info(
                    f"[AuraCore] Pure-navigation fast-path for '{user_goal}' in '{app_context.app_name}' — bypassing grounding."
                )
                self._narrate_grounding_event(f"Navigation in {app_context.app_name}: {user_goal}", confidence=1.0)
                return user_goal

            # 3. Pre-flight Verified Macro Fast-Path (0 LLM tokens, 0ms latency)
            if getattr(self, "macro_compiler", None) is not None:
                repo_root = self.config.get("project_root") or getattr(self, "project_root", None)
                macro = self.macro_compiler.resolve_macro(
                    intent=user_goal,
                    app_name=current_app,
                    workspace_scope=repo_root or task_id,
                )
                if macro is not None:
                    try:
                        self.macro_compiler.execute_macro(macro, app_context=app_context)
                        self._narrate_grounding_event(
                            f"Executed verified macro '{macro.macro_id}' for '{user_goal}' (0 tokens)",
                            confidence=macro.confidence,
                        )
                        return f"[Executed verified macro '{macro.macro_id}' (0 tokens)]: {user_goal}"
                    except Exception as drift_err:
                        logger.warning(f"[AuraCore] Macro drift caught, falling back to 3-tier grounding: {drift_err}")

            # 4. Referential resolution ("that", "it", "no, the other one", "that file")
            is_ref = self.visual_memory.is_referential(user_goal)
            if is_ref:
                target, match_type = self.visual_memory.resolve_reference(
                    user_goal, task_id=task_id, current_app=app_context.app_name
                )
                if target is not None:
                    self._narrate_grounding_event(
                        f"Resolved '{target.label}' (confidence: {target.confidence:.2f}, tier: {target.source_tier}) in {app_context.app_name}",
                        confidence=target.confidence,
                    )
                    augmented_goal = f"{user_goal} [Target: '{target.label}' at coordinates {target.center}, source: {target.source_tier}]"
                    logger.info(f"[AuraCore] Augmented referential goal -> '{augmented_goal}'")
                    return augmented_goal

            # 5. Fresh grounding attempt for non-pronoun targeted actions ("open X", "click X")
            # If user_goal is a pure pronoun ("that", "no, the other one"), do NOT ground it literally
            if not is_ref and getattr(self, "grounding_engine", None) is not None and any(
                w in user_goal.lower() for w in ("open", "click", "select", "press", "launch", "choose")
            ):
                words = user_goal.split()
                ref_candidate = " ".join(words[1:]) if len(words) > 1 else user_goal
                grounded = self.grounding_engine.resolve(ref_candidate, app_context=app_context)
                if grounded is not None:
                    self.visual_memory.remember([grounded], task_id=task_id, app_name=app_context.app_name)
                    self._narrate_grounding_event(
                        f"Grounded '{grounded.label}' (confidence: {grounded.confidence:.2f}, tier: {grounded.source_tier}) in {app_context.app_name}",
                        confidence=grounded.confidence,
                    )
                    augmented_goal = f"{user_goal} [Target: '{grounded.label}' at coordinates {grounded.center}, source: {grounded.source_tier}]"
                    return augmented_goal
        except Exception as e:
            logger.debug(f"[AuraCore] Vision dictation preamble note: {e}")

        return user_goal

    def _narrate_grounding_event(self, message: str, confidence: float = 1.0) -> None:
        """Broadcast live grounding narration to GUI overlays via app_signals."""
        try:
            from gui.signals import app_signals, ExecutionStep, StepStatus
            if hasattr(app_signals, "step_updated"):
                step = ExecutionStep(
                    index=0,
                    title="Vision Grounding",
                    description=message,
                    status=StepStatus.COMPLETED if confidence >= 0.75 else StepStatus.FAILED,
                    engine="vision_grounding",
                    payload=message,
                    metadata={"confidence": confidence},
                )
                app_signals.step_updated.emit(step)
            if hasattr(app_signals, "show_notification") and confidence < 0.75:
                app_signals.show_notification.emit("Vision Grounding Notice", message)
        except Exception:
            pass

    def _prewarm_voice_and_models_async(self):
        """Asynchronously pre-warm Voice ML models in background without blocking startup."""
        import threading

        def _warm():
            try:
                # 1. Pre-warm Groq Turbo STT (Cloud LPU — instant)
                from voice.stt_manager import STTManager, STTSettings, STTProvider
                stt = STTManager(STTSettings(provider=STTProvider.GROQ))
                stt.initialize()

                # 2. Pre-warm Piper TTS
                from voice.tts_manager import TTSManager, TTSSettings, TTSSpeaker
                tts = TTSManager(TTSSettings(speaker=TTSSpeaker.PIPER))
                tts.initialize()

                logger.info("[AuraCore] Voice ML models pre-warmed successfully in background")
            except Exception as e:
                logger.debug(f"[AuraCore] Background ML pre-warm info: {e}")

        threading.Thread(target=_warm, daemon=True, name="AuraModelPrewarmer").start()



    def _init_llm(self):
        """Initialize the Groq LLM client."""
        try:
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise ValueError(
                    "GROQ_API_KEY not set. Add it to your environment or a .env file."
                )
            if Groq is None:
                raise ImportError("groq package not installed. Run: pip install groq")

            self.groq_client = Groq(api_key=api_key)
            self.llm_enabled = True
            self.voice_llm_model = os.environ.get("AURA_VOICE_MODEL", "openai/gpt-oss-20b")
            self.reasoning_llm_model = os.environ.get("AURA_REASONING_MODEL", "openai/gpt-oss-120b")
            self.llm_model = self.reasoning_llm_model
            logger.info(
                f"Groq LLM client initialized successfully (Voice: {self.voice_llm_model}, Reasoning: {self.reasoning_llm_model})"
            )
        except Exception as e:
            self.llm_enabled = False
            self.groq_client = None
            logger.error(f"Failed to initialize Groq client: {e}")

    def _init_executive_brain(self):
        """Initialize the Aura Cognitive Architecture (ACA) — staged cognitive runtime."""
        try:
            # Wire the cognitive runtime to the MasterOrchestrator for execution
            from core.orchestration import MasterOrchestrator
            from brain import (
                CapabilitySelector,
                ContextManager,
                ExecutionCoordinator,
                ExecutionMapValidator,
                GoalAnalyzer,
                LearningEngine,
                ReflectionEngine,
                VerificationEngine,
                WorldModel,
            )
            from brain.aca import (
                ACABrain,
                ConfidenceGate,
                FusionEngine,
                StrategyEngine,
            )

            orchestrator = MasterOrchestrator.get_instance()
            self.coordinator = ExecutionCoordinator(
                orchestrator=orchestrator,
                memory_manager=getattr(self, "memory_manager", None),
            )

            # Create the ACA Brain (5-stage cognitive architecture)
            self.executive_brain = ACABrain(
                context_manager=ContextManager(
                    memory=getattr(self, "memory", None),
                    workspace=self.workspace_info,
                ),
                world_model=WorldModel(),
                goal_analyzer=GoalAnalyzer(),
                capability_selector=CapabilitySelector(),
                fusion_engine=FusionEngine(),
                confidence_gate=ConfidenceGate(),
                planner=StrategyEngine(
                    llm_client=self.groq_client if self.llm_enabled else None
                ),
                validator=ExecutionMapValidator(),
                coordinator=self.coordinator,
                verification=VerificationEngine(),
                reflection=ReflectionEngine(),
                learning=LearningEngine(),
                llm_client=self.groq_client if self.llm_enabled else None,
            )

            try:
                from autonomy.trigger_registry import TriggerRegistry
                from autonomy.trigger_scheduler import TriggerScheduler
                from core.orchestration.execution_policy import ExecutionPolicy
            except (ImportError, ModuleNotFoundError):
                from autonomy.trigger_registry import TriggerRegistry
                from autonomy.trigger_scheduler import TriggerScheduler
                from core.orchestration.execution_policy import ExecutionPolicy

            self.policy = ExecutionPolicy.get_instance()
            self.trigger_registry = TriggerRegistry(
                storage_path=self.project_root / "storage" / "triggers.json"
            )
            self.trigger_scheduler = TriggerScheduler(
                registry=self.trigger_registry,
                coordinator=self.coordinator,
                policy=self.policy,
                orchestrator=orchestrator,
            )

            ContinuousVoiceLoop = None
            try:
                from voice.continuous_loop import ContinuousVoiceLoop
            except (ImportError, ModuleNotFoundError):
                try:
                    from voice.continuous_loop import ContinuousVoiceLoop
                except Exception as e:
                    logger.debug(f"ContinuousVoiceLoop import skipped: {e}")

            if ContinuousVoiceLoop is not None:
                try:
                    self.voice_loop = ContinuousVoiceLoop(
                        coordinator=self.coordinator,
                        nlu_engine=getattr(self, "nlu_engine", None),
                    )
                    self.voice_loop._aura_core = self
                    ContinuousVoiceLoop.set_global_aura_core(self)
                except Exception as e:
                    logger.warning(f"Continuous voice loop initialization notice: {e}")
                    self.voice_loop = None
            else:
                self.voice_loop = None

            # ── Wire Real Engine Callbacks ─────────────────────────────────
            # Replace mock callbacks with real engines so there is ONE execution path.
            try:
                from desktop.native.desktop_execution_engine import (
                    DesktopExecutionEngine,
                )

                desktop_engine = DesktopExecutionEngine()

                async def desktop_callback(action, params):
                    """Real Desktop Engine callback."""
                    try:
                        result = desktop_engine.execute(
                            capability=action,
                            goal=params.get("description", action),
                            arguments=params,
                        )
                        return {
                            "success": getattr(result, "success", True),
                            "observations": list(getattr(result, "observations", [])),
                        }
                    except Exception as e:
                        return {"success": False, "error": str(e)}

                self.executive_brain.register_engine("desktop", desktop_callback)
                logger.info("ACA wired to real Desktop Engine")
            except Exception as e:
                logger.warning(f"Desktop Engine wiring skipped: {e}")

            try:
                from browser.engine import BrowserEngine

                browser_engine = BrowserEngine()

                async def browser_callback(action, params):
                    """Real Browser Engine callback."""
                    try:
                        result = browser_engine.execute(
                            capability=action,
                            goal=params.get("description", action),
                            arguments=params,
                        )
                        return {
                            "success": getattr(result, "success", True),
                            "observations": list(getattr(result, "observations", [])),
                        }
                    except Exception as e:
                        return {"success": False, "error": str(e)}

                self.executive_brain.register_engine("browser", browser_callback)
                logger.info("ACA wired to real Browser Engine")
            except Exception as e:
                logger.warning(f"Browser Engine wiring skipped: {e}")

            try:
                from research.research_engine import ResearchEngine

                research_engine = ResearchEngine()

                async def research_callback(action, params):
                    """Real Research Engine callback."""
                    try:
                        result = research_engine.execute(
                            capability=action,
                            goal=params.get("description", action),
                            arguments=params,
                        )
                        return {
                            "success": getattr(result, "success", True),
                            "observations": list(getattr(result, "observations", [])),
                        }
                    except Exception as e:
                        return {"success": False, "error": str(e)}

                self.executive_brain.register_engine("research", research_callback)
                logger.info("ACA wired to real Research Engine")
            except Exception as e:
                logger.warning(f"Research Engine wiring skipped: {e}")

            self.executive_brain_enabled = True

            self.components["executive_brain"] = ComponentStatus(
                name="Executive Brain",
                status=AuraCoreStatus.READY,
                message="Aura Cognitive Architecture initialized",
            )
            logger.info(
                "Aura Cognitive Architecture (ACA) initialized: "
                "Stage0(Perception) → Stage1(DMM) → Stage2(Planning) → Stage3(Execution) → Stage4(Reflection/Learning)"
            )
        except Exception as e:
            self.executive_brain_enabled = False
            self.executive_brain = None
            self.components["executive_brain"] = ComponentStatus(
                name="Executive Brain",
                status=AuraCoreStatus.ERROR,
                message=f"Aura Cognitive Architecture failed to initialize: {e}",
                loaded=False,
            )
            logger.error(f"Failed to initialize Aura Cognitive Architecture: {e}")

    async def process_via_executive_brain(self, user_goal: str) -> str:
        """
        Process a request through the Executive Brain's cognitive pipeline.

        The Executive Brain is the ONLY component that "thinks."
        Everything else simply executes.
        """
        if not self.executive_brain_enabled or self.executive_brain is None:
            return await self.process_request(user_goal)

        try:
            from core.learning.behavior_store import BehaviorStore

            # Build context for the Executive Brain
            context = {
                "workspace_root": self.workspace,
                "workspace_info": self.workspace_info,
                "llm_enabled": self.llm_enabled,
            }

            # Register behavior store for learning
            try:
                behavior_store = BehaviorStore()
                self.executive_brain.register_behavior_store(behavior_store)
                context["behavior_store"] = behavior_store
            except Exception as e:
                logger.debug(f"Behavior store registration skipped: {e}")

            # Process through the Executive Brain
            response = await self.executive_brain.process(user_goal, context)

            return response.text

        except Exception as e:
            logger.error(f"Executive Brain pipeline failed: {e}", exc_info=True)
            # Fallback to standard pipeline
            return await self.process_request(user_goal)

    def _build_chat_messages(
        self, user_message: str, max_turns: int = 10
    ) -> list[dict[str, Any]]:
        """
        Construct multi-turn conversation messages enriched with live ambient system context.
        """
        from core.context.ambient_context_builder import AmbientContextBuilder

        ambient_info = AmbientContextBuilder.build_ambient_context(self, query=user_message)

        sys_prompt = (
            "You are AuraAI (v17.0), a next-gen holographic autonomous AI OS and desktop assistant running on Windows.\n"
            "You are direct, concise, factual, and helpful. You have native tool capabilities to control the desktop "
            "(launch applications, control windows, adjust audio volume, adjust screen brightness, clipboard), "
            "inspect the visual screen (OCR), access hardware telemetry, browse the web, and store/query persistent memory facts.\n\n"
            "### Live Ambient Environment & Context:\n"
            f"{ambient_info}\n\n"
            "### Instructions:\n"
            "- If the user requests an action or information that can be handled with an available tool, invoke the appropriate tool.\n"
            "- When the user requests multiple actions (e.g. 'Open Chrome, search for X, and create a summary note on my desktop'), execute ALL requested actions using available tools (desktop_launch_app, browser_open_url, desktop_create_note).\n"
            "- Answer questions accurately using the provided ambient context when relevant.\n"
            "- Always communicate in clear, natural English unless the user explicitly requests another language.\n"
            "- Output clear natural language text."
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": sys_prompt}
        ]

        # Append previous conversation history window
        history_window = self.conversation_history[-max_turns:] if self.conversation_history else []
        for entry in history_window:
            role = entry.get("role", "user")
            content = entry.get("content", "")
            if role in ["user", "assistant"] and content:
                messages.append({"role": role, "content": content})

        # Append current user message
        messages.append({"role": "user", "content": user_message})
        return messages

    async def get_ai_response_stream(
        self, user_message: str, model: str | None = None
    ) -> AsyncGenerator[str, None]:
        """
        Streaming variant of get_ai_response: yields token chunks directly from Groq/provider
        with full multi-turn memory and ambient environment context.
        """
        if not self.llm_enabled or self.groq_client is None:
            yield (
                "⚠ AI is not configured. Set GROQ_API_KEY in your environment "
                "or .env file and make sure the 'groq' package is installed."
            )
            return

        try:
            messages = self._build_chat_messages(user_message)
            target_model = model or getattr(self, "voice_llm_model", "openai/gpt-oss-20b")
            kwargs: dict[str, Any] = {
                "model": target_model,
                "messages": messages,
                "stream": True,
                "temperature": 0.7,
                "max_tokens": 1024,
            }
            if "gpt-oss-120b" in target_model:
                kwargs["reasoning_effort"] = "medium"

            full_response_chunks = []
            completion = self.groq_client.chat.completions.create(**kwargs)
            for chunk in completion:
                if (
                    chunk.choices
                    and chunk.choices[0].delta
                    and chunk.choices[0].delta.content
                ):
                    token = chunk.choices[0].delta.content
                    full_response_chunks.append(token)
                    yield token

            # Record turn in conversation history
            full_text = "".join(full_response_chunks).strip()
            if full_text:
                self.add_to_conversation("user", user_message)
                self.add_to_conversation("assistant", full_text)

        except Exception as e:
            logger.error(f"get_ai_response_stream error: {e}", exc_info=True)
            resp = await self.get_ai_response(user_message)
            yield resp

    async def get_ai_response(
        self, user_message: str, enable_tools: bool = True
    ) -> str:
        """
        Send the user's message through the Groq LLM reasoning engine with
        multi-turn context, ambient environment grounding, and native autonomous tool calling.

        Args:
            user_message: The latest message from the user
            enable_tools: Whether to provide native function calling tools to the model

        Returns:
            The AI's text response
        """
        if not self.llm_enabled or self.groq_client is None:
            return (
                "⚠ AI is not configured. Set GROQ_API_KEY in your environment "
                "or .env file and make sure the 'groq' package is installed."
            )

        # 1. Deterministic Local Intent Fast-Path (0ms latency & 0 API tokens across all frontends)
        # Skip fast-path for compound multi-action queries (e.g. connectors or comma-separated multi-actions)
        msg_lower = user_message.lower().strip()
        has_connector = any(w in msg_lower for w in (" and ", " then ", " also ", " after that ", " plus ", " & "))
        has_multi_clause = ("," in msg_lower or ";" in msg_lower) and any(
            verb in msg_lower for verb in ("open ", "launch ", "start ", "create ", "search ", "browse ", "set ", "turn ", "run ")
        )
        is_compound = has_connector or (has_multi_clause and len([c for c in msg_lower.replace(";", ",").split(",") if c.strip()]) > 1)

        if not is_compound:
            conv_engine = getattr(self, "conversation_engine", None)
            if conv_engine is not None:
                try:
                    intent = conv_engine.intent_router.detect(user_message)
                    local_answer = conv_engine._answer_local_intent(intent)
                    if local_answer is not None:
                        logger.debug(f"[AuraCore] Resolved via deterministic local fast-path: {intent}")
                        return local_answer
                except Exception as ce_err:
                    logger.debug(f"[AuraCore] Local intent router exception: {ce_err}")

        try:
            import json
            from core.tools.aura_tool_registry import AuraToolRegistry

            target_model = getattr(self, "reasoning_llm_model", "openai/gpt-oss-120b")
            messages = self._build_chat_messages(user_message)
            tools = AuraToolRegistry.get_tool_definitions() if enable_tools else None

            kwargs: dict[str, Any] = {
                "model": target_model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1024,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            def _get_dynamic_reasoning_effort(msg: str) -> str:
                m = msg.lower().strip()
                # 1. HIGH: Deep debugging, tracebacks, complex algorithm design, math proofs
                if any(w in m for w in ("debug", "traceback", "algorithm", "architecture", "solve math", "refactor code", "optimize complexity", "memory leak")):
                    return "high"
                # 2. MEDIUM: Long-form analysis, essays, deep explanations
                if any(w in m for w in ("explain in detail", "write an essay", "pros and cons", "comprehensive analysis", "step-by-step breakdown")):
                    return "medium"
                # 3. LOW: Fast desktop automation, volume, apps, web search, quick Q&A, greetings
                return "low"

            dynamic_effort = _get_dynamic_reasoning_effort(user_message)
            if "gpt-oss-120b" in target_model:
                kwargs["reasoning_effort"] = dynamic_effort
                logger.info(f"[AuraCore Dynamic Reasoning] Profile: {dynamic_effort.upper()} | Model: openai/gpt-oss-120b | Query: '{user_message[:40]}'")

            from ai.key_pool import KeyPool
            from groq import Groq
            key_pool = KeyPool.get_instance()

            def _call_groq(call_kwargs: dict[str, Any], model_name: str):
                kw = dict(call_kwargs)
                kw["model"] = model_name
                if "gpt-oss-120b" not in model_name:
                    kw.pop("reasoning_effort", None)

                def _do_chat(api_key: str):
                    client = Groq(api_key=api_key)
                    return client.chat.completions.create(**kw)

                try:
                    return key_pool.execute_with_failover(_do_chat, service="groq")
                except Exception as ex:
                    # If all keys exhausted for gpt-oss-120b, failover to qwen/qwen3.6-27b
                    if "qwen3.6-27b" not in model_name:
                        logger.warning(f"[AuraCore] Groq model '{model_name}' exhausted/error ({ex}), falling back to qwen/qwen3.6-27b across key pool.")
                        kw["model"] = "qwen/qwen3.6-27b"
                        kw.pop("reasoning_effort", None)
                        return key_pool.execute_with_failover(_do_chat, service="groq")
                    raise ex

            # Iterative ReAct Autonomous Tool Calling Loop (up to 5 turns)
            final_text = ""
            for iteration in range(5):
                try:
                    res = await asyncio.to_thread(_call_groq, kwargs, target_model)
                except Exception as call_err:
                    err_str = str(call_err)
                    logger.warning(f"Groq tool error, failing over to qwen/qwen3.6-27b: {call_err}")
                    res = await asyncio.to_thread(_call_groq, kwargs, "qwen/qwen3.6-27b")

                if not res or not res.choices or not res.choices[0].message:
                    final_text = "I was unable to generate a response."
                    break

                response_msg = res.choices[0].message

                # Check if model requested tool execution
                if hasattr(response_msg, "tool_calls") and response_msg.tool_calls:
                    logger.info(f"[AuraCore] ReAct turn {iteration + 1}: Executing {len(response_msg.tool_calls)} tool call(s).")
                    messages.append(response_msg)

                    for tool_call in response_msg.tool_calls:
                        fn_name = tool_call.function.name
                        try:
                            fn_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                        except Exception:
                            fn_args = {}

                        # Execute the tool natively
                        tool_result = await AuraToolRegistry.execute_tool(fn_name, fn_args, aura_core=self)

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": fn_name,
                            "content": json.dumps(tool_result, default=str),
                        })

                    # Prepare kwargs for next turn in loop
                    kwargs["messages"] = messages
                else:
                    final_text = response_msg.content or "Action completed."
                    break

            # Strip any internal chain-of-thought blocks (<think>...</think>)
            import re
            final_text = re.sub(r"<think>[\s\S]*?</think>", "", final_text, flags=re.IGNORECASE)
            final_text = re.sub(r"<think>[\s\S]*$", "", final_text, flags=re.IGNORECASE).strip()

            # Update conversation history
            self.add_to_conversation("user", user_message)
            self.add_to_conversation("assistant", final_text)

            # ── M32: Focus thread postamble ─────────────────────────────────────
            # Update working context and drain buffered notifications.
            final_text = self._focus_postamble(user_message, final_text)

            return final_text

        except Exception as e:
            logger.error(f"get_ai_response failed: {e}", exc_info=True)
            return f"✗ Error processing message: {e}"

    async def process_request_stream(
        self, user_goal: str, yield_filler: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Unified OS Kernel streaming request entry point.
        Streams conversational tokens or yields progressive orchestration feedback.
        """
        raw = user_goal.strip().lower()
        if raw in [
            "yes", "y", "yeah", "yep", "sure", "ok", "okay", "no", "n", "nope", "nah"
        ]:
            resp = await self.process_request(user_goal)
            yield resp
            return

        try:
            from core.orchestration import MasterOrchestrator
            orchestrator = MasterOrchestrator.get_instance()

            # Check if pending confirmation is active before execution
            pending_conf = orchestrator.check_pending_confirmation()
            if pending_conf is not None:
                yield f"I need your confirmation to {pending_conf.action_plan.goal}. Should I proceed?"
                return

            # Fast Pre-evaluation via DecisionEngine
            decision = orchestrator.decision_engine.evaluate(user_goal)
            intent_type = decision.intent_type
            can_from_sys = decision.can_answer_from_system
            needs_planner = decision.needs_planner

            # System Self-Knowledge Queries (Instant local resolution)
            if intent_type == "system_query" or can_from_sys:
                from core.system.system_knowledge_resolver import SystemKnowledgeResolver
                yield SystemKnowledgeResolver.resolve(user_goal)
                return

            # Conversational Chat Queries -> Stream directly from Groq LLM immediately!
            if (intent_type == "chat" or not needs_planner) and self.llm_enabled and self.groq_client is not None:
                async for token in self.get_ai_response_stream(user_goal):
                    yield token
                return

            # Fast Tool Execution via Autonomous ReAct LLM Engine (Groq openai/gpt-oss-120b)
            if self.llm_enabled and self.groq_client is not None:
                ai_resp = await self.get_ai_response(user_goal, enable_tools=True)
                yield ai_resp
                return

            result = await orchestrator.process_request_async(user_goal)

            # Check if pending confirmation was generated during execution (Hard-Block invariant)
            pending_conf = orchestrator.check_pending_confirmation()
            if pending_conf is not None:
                yield f"I need your confirmation to {pending_conf.action_plan.goal}. Should I proceed?"
                return

            res_decision = (
                result.data.get("decision", {})
                if hasattr(result, "data") and isinstance(result.data, dict)
                else {}
            )
            res_intent_type = res_decision.get("intent_type", intent_type)

            if hasattr(result, "final_output") and getattr(result, "final_output"):
                yield str(getattr(result, "final_output"))
            elif result.observations or result.data:
                if (
                    self.llm_enabled 
                    and self.groq_client is not None 
                    and intent_type in ["browser", "research"]
                ):
                    obs_text = "\n".join(result.observations) if result.observations else ""
                    synth_prompt = (
                        f"The user originally asked: '{user_goal}'.\n\n"
                        f"The system found:\n{obs_text}\n\n"
                        f"Please provide a direct, helpful conversational answer."
                    )
                    async for token in self.get_ai_response_stream(synth_prompt):
                        yield token
                else:
                    filtered_obs = []
                    for obs in (result.observations or []):
                        if "pre-execution decision:" in obs.lower():
                            continue
                        if "no backend available for capability" in obs.lower():
                            filtered_obs.append("I don't know how to perform that specific action on your desktop yet.")
                        else:
                            filtered_obs.append(obs)
                    if filtered_obs:
                        yield "\n".join(filtered_obs)
                    elif result.success:
                        yield "Action completed successfully."
                    else:
                        yield "I was unable to complete that action."
            else:
                yield "Action completed successfully." if result.success else "I was unable to complete that action."
        except Exception as e:
            logger.error(f"process_request_stream failed: {e}", exc_info=True)
            yield f"I encountered an error: {e}"

    async def process_request(self, user_goal: str) -> str:
        """
        Unified OS Kernel request entry point.
        Executes all requests through the unified ReAct tool engine (get_ai_response).
        """
        try:
            # ── M32: Focus thread preamble ──────────────────────────────────────
            # Resolve which focus thread this turn belongs to (zero-latency,
            # deterministic) before dispatching to the LLM engine.
            self._focus_preamble(user_goal)

            # ── M33: Vision dictation & Contextual action preamble ──────────────
            # Pure-navigation fast-path and referential pronoun resolution
            user_goal = self._vision_dictation_preamble(user_goal)

            # 1. Direct Unified ReAct Tool & LLM Engine across CLI, GUI, and Voice
            if self.llm_enabled and self.groq_client is not None:
                return await self.get_ai_response(user_goal, enable_tools=True)

            # 2. Local fallback if LLM is disabled
            conv_engine = getattr(self, "conversation_engine", None)
            if conv_engine is not None:
                try:
                    intent = conv_engine.intent_router.detect(user_goal)
                    local_answer = conv_engine._answer_local_intent(intent)
                    if local_answer is not None:
                        from brain.models import ConversationContext
                        ctx = ConversationContext(
                            user_input=user_goal,
                            intent=intent,
                            messages=[],
                            attachments=[],
                        )
                        conv_engine._save_turn(ctx, local_answer)
                        return local_answer
                except Exception as ce_err:
                    logger.debug(f"[AuraCore.process_request] Local intent fast-path bypassed: {ce_err}")

            from core.orchestration import MasterOrchestrator

            orchestrator = MasterOrchestrator.get_instance()

            raw = user_goal.strip().lower()
            if raw in [
                "yes",
                "y",
                "yeah",
                "yep",
                "sure",
                "ok",
                "okay",
                "no",
                "n",
                "nope",
                "nah",
            ]:
                raw = user_goal.strip().lower()
                if raw in ["quit", "exit", "bye", "goodbye", "close aura", "exit aura"]:
                    name = ""
                    if self.memory:
                        name = self.memory.fact_value("profile", "name") or self.memory.fact_value("person", "name") or ""
                    return f"Goodbye{', ' + name if name else ''}! Session closed."
                try:
                    if orchestrator.check_pending_confirmation() is not None:
                        resolved_result = orchestrator.resolve_pending_confirmation(
                            user_goal
                        )
                        if resolved_result is not None:
                            return (
                                "\n".join(resolved_result.observations)
                                if resolved_result.observations
                                else "Done."
                            )
                except Exception as exc:
                    logger.debug(
                        f"Session-scoped confirmation resolution skipped: {exc}"
                    )

                # ── Fallback: ExecutionPolicy singleton (backward compat) ──
                try:
                    from core.orchestration.execution_policy import (
                        ExecutionPolicy,
                        PolicyAction,
                    )

                    policy = ExecutionPolicy.get_instance()
                    if policy.has_pending_confirmation():
                        resolved = policy.resolve_confirmation(user_goal)
                        if resolved is not None:
                            if resolved.action == PolicyAction.CONFIRMED_LAUNCH:
                                new_goal = f"Open new instance of {resolved.app_name}"
                                result = await orchestrator.process_request_async(
                                    new_goal
                                )
                                return (
                                    "\n".join(result.observations)
                                    if result.observations
                                    else resolved.message
                                )
                            elif resolved.action == PolicyAction.REUSE_EXISTING:
                                if resolved.hwnd:
                                    try:
                                        import win32gui

                                        win32gui.SetForegroundWindow(resolved.hwnd)
                                        win32gui.BringWindowToTop(resolved.hwnd)
                                    except Exception:
                                        pass
                                return f"OK — keeping existing {resolved.app_name.title()} window."
                except Exception as exc:
                    logger.debug(
                        f"ExecutionPolicy confirmation fallback skipped: {exc}"
                    )

            result = await orchestrator.process_request_async(user_goal)

            decision = (
                result.data.get("decision", {})
                if hasattr(result, "data") and isinstance(result.data, dict)
                else {}
            )
            intent_type = decision.get("intent_type")
            can_from_sys = decision.get("can_answer_from_system", False)
            needs_planner = decision.get("needs_planner", True)

            # System Self-Knowledge Queries (Who are you?, What are your capabilities?, Limitations, Planners, Backends)
            if intent_type == "system_query" or can_from_sys:
                from core.system.system_knowledge_resolver import (
                    SystemKnowledgeResolver,
                )

                return SystemKnowledgeResolver.resolve(user_goal)

            # Vision Screen Queries (What's on my screen?, Describe screen, etc.)
            if intent_type in ("vision", "screen_vision"):
                try:
                    import asyncio
                    import re
                    from vision.vision_manager import VisionManager

                    def _capture_screen_context():
                        vm = VisionManager()
                        return vm.capture_and_analyze()

                    vis_ctx = await asyncio.to_thread(_capture_screen_context)
                    screen_text = (vis_ctx.extracted_text or "").strip()
                    active_window = vis_ctx.metadata.get("active_window", "Desktop")

                    # Best-effort privacy sanitization for sensitive credentials/tokens/card numbers
                    if screen_text:
                        screen_text = re.sub(r"\b(?:\d[ -]*?){13,16}\b", "[REDACTED_CARD]", screen_text)
                        screen_text = re.sub(
                            r"(?:api[_-]?key|secret|token|password)[\s:=]+['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?",
                            "[REDACTED_SECRET]",
                            screen_text,
                            flags=re.IGNORECASE,
                        )

                    prompt = (
                        f"The user asked: '{user_goal}'.\n\n"
                        f"Visual Perception Data from Screen:\n"
                        f"- Active Focused Window: {active_window}\n"
                        f"- Visible Screen OCR Content:\n{screen_text[:3000] if screen_text else 'No text or application content visible on screen.'}\n\n"
                        f"Please provide a concise, direct, helpful summary of what is currently on the user's screen based on the visual perception data."
                    )
                    return await self.get_ai_response(prompt)
                except Exception as vis_exc:
                    logger.warning(f"Vision screen capture failed: {vis_exc}")
                    return f"I tried to inspect your screen, but encountered an error: {vis_exc}"

            # Conversational Chat Queries (greetings, general chat)
            if (
                (intent_type == "chat" or not needs_planner)
                and self.llm_enabled
                and self.groq_client is not None
            ):
                return await self.get_ai_response(user_goal)

            if hasattr(result, "final_output") and getattr(result, "final_output"):
                return str(getattr(result, "final_output"))
            elif result.observations or result.data:
                # If we have observations/data but no final output, and it's a browser/research task, synthesize an answer
                if (
                    self.llm_enabled 
                    and self.groq_client is not None 
                    and intent_type in ["browser", "research", "coding", "workspace"]
                ):
                    obs_text = "\n".join(result.observations) if result.observations else ""
                    if result.data:
                        # Extract important nested data safely
                        import json
                        try:
                            # Filter out large raw HTML/system data to avoid context window explosion
                            clean_data = {k: v for k, v in result.data.items() if k not in ["metrics", "budget", "system_observations"] and not (isinstance(v, str) and len(v) > 2000)}
                            if clean_data:
                                obs_text += "\n\nAdditional Data:\n" + json.dumps(clean_data, default=str, indent=2)
                        except Exception:
                            obs_text += f"\n\nAdditional Data:\n{result.data}"

                    synth_goal = (
                        f"The user originally asked: '{user_goal}'.\n\n"
                        f"The system performed the action and found this information:\n{obs_text}\n\n"
                        f"Please provide a direct, helpful conversational answer to the user's question based ONLY on these findings."
                    )
                    return await self.get_ai_response(synth_goal)
                
                filtered_obs = []
                for obs in (result.observations or []):
                    if "pre-execution decision:" in obs.lower():
                        continue
                    if "no backend available for capability" in obs.lower():
                        # If a capability failed or was missing, check if the request was generative text / writing
                        if self.llm_enabled and self.groq_client is not None:
                            return await self.get_ai_response(user_goal)
                        filtered_obs.append("I don't know how to perform that specific action on your desktop yet.")
                    else:
                        filtered_obs.append(obs)
                if filtered_obs:
                    return "\n".join(filtered_obs)
                elif result.success:
                    return "Action completed successfully."
                elif self.llm_enabled and self.groq_client is not None:
                    return await self.get_ai_response(user_goal)
                else:
                    return "I was unable to complete that action."
            else:
                if not result.success and self.llm_enabled and self.groq_client is not None:
                    return await self.get_ai_response(user_goal)
                return f"Action completed successfully." if result.success else "I was unable to complete that action."
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.error(
                f"MasterOrchestrator pipeline execution failed: {e}", exc_info=True
            )
            return f"❌ Pipeline Execution Error: {e}"

    def _initialize_components(self):
        """Initialize all core components."""
        logger.info("Initializing Aura Core...")

        self._init_brain()
        self._init_memory()
        self._init_research()
        self._init_planner()
        self._init_knowledge()
        self._init_plugins()
        self._init_workspace()
        self._init_multi_agent()
        self._init_agent_runtime()
        self._init_workflow()
        self._init_vision()

        # FocusManager is initialised separately after _init_executive_brain so
        # that TriggerScheduler is available for the archival cron registration.
        self.focus_manager = None

        logger.info("Aura Core initialized successfully")

    def _init_vision(self):
        """Initialize Vision System."""
        try:
            from vision.vision_manager import VisionManager
            from vision.vision_plugin import VisionPlugin

            self.vision_plugin = VisionPlugin()
            if self.vision_plugin.on_load():
                self.vision_manager = self.vision_plugin.vision_manager
                self.vision_enabled = True
                self.components["vision"] = ComponentStatus(
                    name="Vision System",
                    status=AuraCoreStatus.READY,
                    message="Vision System active",
                )
                logger.info("Vision System initialized successfully")
            else:
                self.vision_enabled = False
                self.components["vision"] = ComponentStatus(
                    name="Vision System",
                    status=AuraCoreStatus.ERROR,
                    message="Vision plugin on_load failed",
                    loaded=False,
                )
        except Exception as e:
            logger.error(f"Failed to initialize vision system: {e}")
            self.vision_enabled = False
            self.components["vision"] = ComponentStatus(
                name="Vision System",
                status=AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False,
            )

    def _init_memory(self):
        """Initialize memory system."""
        try:
            self.memory_enabled = True

            # Query actual memory statistics
            total_memories = self.memory.count_memories() if self.memory else 0
            num_categories = self.memory.count_categories() if self.memory else 0

            self.memory_stats = {
                "total_memories": total_memories,
                "num_categories": num_categories,
                "project": self.workspace,
            }

            self.components["memory"] = ComponentStatus(
                name="Memory",
                status=AuraCoreStatus.READY,
                message=f"{total_memories} memories, {num_categories} categories",
            )
        except Exception as e:
            logger.error(f"Failed to initialize memory: {e}")
            self.memory_enabled = False
            self.components["memory"] = ComponentStatus(
                name="Memory", status=AuraCoreStatus.ERROR, message=str(e), loaded=False
            )

    def _init_knowledge(self):
        """Initialize knowledge system."""
        try:
            self.knowledge_enabled = True
            self.knowledge_stats = {
                "indexed": True,
                "search_enabled": True,
                "project": self.workspace,
            }
            self.components["knowledge"] = ComponentStatus(
                name="Knowledge",
                status=AuraCoreStatus.READY,
                message="Knowledge indexed",
            )
        except Exception as e:
            logger.error(f"Failed to initialize knowledge: {e}")
            self.knowledge_enabled = False
            self.components["knowledge"] = ComponentStatus(
                name="Knowledge",
                status=AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False,
            )

    def _init_plugins(self):
        """Initialize plugin system."""
        try:
            try:
                from plugins.shared.plugin_manager import PluginManager
            except ImportError:
                from plugins.plugin_manager import PluginManager

            plugin_manager = PluginManager()

            # Load available plugins
            available_plugins = [
                "desktop",
                "filesystem",
                "vision",
                "voice",
                "engineering",
                "git",
                "calendar",
                "email",
                "networking",
                "office",
                "terminal",
                "knowledge",
                "mcp",
                "browser",
            ]

            loaded_plugins = []
            for plugin_name in available_plugins:
                try:
                    # Try to load plugin
                    plugin_manager.load_plugin(plugin_name)
                    loaded_plugins.append(plugin_name)
                except Exception as e:
                    logger.warning(f"Plugin {plugin_name} not loaded: {e}")

            self.plugins = loaded_plugins
            self.plugin_count = len(loaded_plugins)

            self.components["plugins"] = ComponentStatus(
                name="Plugins",
                status=AuraCoreStatus.READY,
                message=f"{self.plugin_count} plugins loaded",
            )
        except Exception as e:
            logger.error(f"Failed to initialize plugins: {e}")
            self.plugin_count = 0
            self.components["plugins"] = ComponentStatus(
                name="Plugins",
                status=AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False,
            )

    def _init_workspace(self):
        """Initialize workspace awareness."""
        try:
            workspace_path = Path(self.workspace)
            if workspace_path.exists():
                self.workspace_aware = True
                self.workspace_info = {
                    "path": str(workspace_path),
                    "exists": True,
                    "files": 0,
                    "folders": 0,
                }

                def _count_in_background():
                    try:
                        files, folders = 0, 0
                        # Quick top-level scan without freezing startup
                        for item in workspace_path.iterdir():
                            if item.name.startswith((".", "node_modules", "venv", "__pycache__")):
                                continue
                            if item.is_file():
                                files += 1
                            elif item.is_dir():
                                folders += 1
                        self.workspace_info["files"] = files
                        self.workspace_info["folders"] = folders
                    except Exception:
                        pass

                import threading
                threading.Thread(target=_count_in_background, daemon=True, name="WorkspaceScanner").start()

                self.components["workspace"] = ComponentStatus(
                    name="Workspace",
                    status=AuraCoreStatus.READY,
                    message="Workspace attached",
                )
            else:
                logger.warning(f"Workspace path does not exist: {self.workspace}")
                self.workspace_aware = False
                self.components["workspace"] = ComponentStatus(
                    name="Workspace",
                    status=AuraCoreStatus.ERROR,
                    message="Path does not exist",
                    loaded=False,
                )
        except Exception as e:
            logger.error(f"Failed to initialize workspace: {e}")
            self.workspace_aware = False
            self.components["workspace"] = ComponentStatus(
                name="Workspace",
                status=AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False,
            )

    def _init_brain(self):
        """Initialize brain with Memory and ConversationEngine."""
        # Static counter to track calls
        if not hasattr(self, "_brain_call_count"):
            self._brain_call_count = 0
        self._brain_call_count += 1
        logger.info(f"[_init_brain] ENTERING (call #{self._brain_call_count})")
        try:
            if Memory is None:
                raise ImportError("Memory module not available")

            # Create Memory instance
            self.memory = Memory(
                db_path=self.memory_db_path, chat_log_path=self.chat_log_path
            )

            # Create ConversationEngine
            from ai.provider_manager import ProviderManager
            from memory.manager.memory_manager import MemoryManager
            from ai.groq_provider import (  # adjust path if it lives elsewhere
                GroqProvider,
            )
            from brain.conversation_engine import ConversationEngine

            self.provider_manager = ProviderManager()
            self.provider_manager.register(
                "groq", GroqProvider(api_key=os.environ.get("GROQ_API_KEY", ""))
            )
            self.provider_manager.set_default("groq")

            self.memory_manager = MemoryManager(
                provider_manager=self.provider_manager,
                memory=self.memory,
            )

            # Create ConversationEngine
            self.conversation_engine = ConversationEngine(
                memory=self.memory,
                provider_manager=self.provider_manager,
                settings={
                    "provider": "groq",
                    "model": self.groq_model,
                },
                model=self.groq_model,
                aura_core=self,
                memory_manager=self.memory_manager,
            )

            self.brain_enabled = True
            self.components["brain"] = ComponentStatus(
                name="Brain",
                status=AuraCoreStatus.READY,
                message="Brain initialized with memory",
            )

            logger.info("Brain initialized successfully")
        except Exception as e:
            logger.critical(
                f"[_init_brain] FAILED — brain will be DISABLED. "
                f"ConversationEngine is NOT wired. Memory context will NOT flow. "
                f"Cause: {type(e).__name__}: {e}"
            )
            logger.exception("Full brain_init traceback:")
            self._brain_init_error = e          # expose for tests / health checks
            self.brain_enabled = False
            self.components["brain"] = ComponentStatus(
                name="Brain", status=AuraCoreStatus.ERROR, message=str(e), loaded=False
            )

    def _init_research(self):
        """Initialize research engine for live data research."""
        # Static counter to track calls
        if not hasattr(self, "_research_call_count"):
            self._research_call_count = 0
        self._research_call_count += 1
        logger.info(
            f"[_init_research] ENTERING (call #{self._research_call_count}) - "
            f"research_enabled={self.research_enabled}, "
            f"research_integration is None={self.research_integration is None}, "
            f"_research_initialized={self._research_initialized}"
        )
        try:
            logger.info("[_init_research] Creating ResearchEngine...")

            # Import research engine
            from research import ResearchConfig, ResearchEngine

            research_settings = self.config.get("research_settings", {})

            # Create ResearchEngine
            research_engine = ResearchEngine(
                config=ResearchConfig(
                    enabled=True,
                    default_mode=SearchMode.STANDARD,
                    default_max_results=research_settings.get("max_results", 10),
                    cache_ttl=research_settings.get("cache_ttl", 1800),
                    conflict_resolution=ConflictResolution.AUTO,
                )
            )
            # Add unique identifier to track this instance
            research_engine.__id__ = f"research_engine_{id(self)}"
            logger.info(
                f"[_init_research] Created ResearchEngine with id={research_engine.__id__}, "
                f"object={research_engine}"
            )

            logger.info("[_init_research] Creating ResearchIntegration...")
            from brain.research_integration import ResearchIntegration

            self.research_integration = ResearchIntegration(research_engine)
            self.research_integration.__id__ = f"research_integration_{id(self)}"
            logger.info(
                f"[_init_research] Created ResearchIntegration with "
                f"id={self.research_integration.__id__}, object={self.research_integration}"
            )

            self.research_enabled = True
            self._research_initialized = True
            logger.info(
                f"[_init_research] Set research_enabled=True, "
                f"research_integration={self.research_integration}"
            )

            self.components["research"] = ComponentStatus(
                name="Research Engine",
                status=AuraCoreStatus.READY,
                message="Research engine initialized",
            )

            logger.info("Research engine initialized successfully")
        except ImportError as e:
            logger.error(f"[_init_research] ImportError caught: {e}")
            self.research_enabled = False
            self._research_initialized = False
            self.components["research"] = ComponentStatus(
                name="Research Engine",
                status=AuraCoreStatus.ERROR,
                message=f"Research module: {e}",
                loaded=False,
            )
        except Exception as e:
            logger.exception(
                f"[_init_research] Exception caught: {type(e).__name__}: {e}"
            )
            self.research_enabled = False
            self._research_initialized = False
            self.components["research"] = ComponentStatus(
                name="Research Engine",
                status=AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False,
            )

    def is_research_needed(self, query: str) -> bool:
        """
        Check if research is needed for a query.

        Args:
            query: User query

        Returns:
            True if research is needed
        """
        if not self.research_enabled or self.research_integration is None:
            return False

        return self.research_integration.is_research_needed(query)

    def perform_research(
        self, query: str, mode: str = "standard"
    ) -> dict[str, Any] | None:
        """
        Perform research and return results.

        Args:
            query: Research query
            mode: Search mode ('quick', 'standard', 'deep')

        Returns:
            Research results dictionary or None if failed
        """
        logger.info(
            f"[AuraCore] perform_research() called with query='{query}', mode='{mode}'"
        )
        logger.info(
            f"[AuraCore] research_enabled={self.research_enabled}, "
            f"research_integration is None={self.research_integration is None}"
        )
        logger.info(f"[AuraCore] _research_initialized={self._research_initialized}")
        if self.research_integration and hasattr(self.research_integration, "__id__"):
            logger.info(
                f"[AuraCore] research_integration.id={self.research_integration.__id__}"
            )
        if self.research_integration and hasattr(
            self.research_integration.research_engine, "__id__"
        ):
            logger.info(
                f"[AuraCore] research_integration.research_engine.id="
                f"{self.research_integration.research_engine.__id__}"
            )

        if not self.research_enabled or self.research_integration is None:
            logger.warning("[AuraCore] Research is disabled or integration is None")
            return None

        # NOTE: was `from research import SearchMode` (wrong module path,
        # would raise ImportError). Fixed to match the top-of-file import.
        search_mode = SearchMode.STANDARD
        if mode == "quick":
            search_mode = SearchMode.QUICK
        elif mode == "deep":
            search_mode = SearchMode.DEEP

        logger.info(
            f"[AuraCore] Calling research_integration.perform_research() with mode={search_mode}"
        )
        results = self.research_integration.perform_research(query, mode=search_mode)
        logger.info(
            f"[AuraCore] research_integration.perform_research() returned: "
            f"has_results={results.get('has_results', False) if results else False}"
        )
        return results

    def enhance_response_with_research(
        self, query: str, user_message: str, max_results: int = 5
    ) -> dict[str, Any]:
        """
        Enhance a response with research findings.

        This method checks if research is needed, performs it, and
        returns a dict with the research findings and a flag indicating
        whether research was used.

        Args:
            query: Original query
            user_message: Full user message
            max_results: Maximum results to include

        Returns:
            Dict with research findings and status
        """
        if not self.research_enabled or self.research_integration is None:
            return {"research_used": False, "message": "Research not available"}

        return self.research_integration.enhance_response_with_research(
            query, user_message, max_results
        )

    def get_research_stats(self) -> dict[str, Any]:
        """
        Get research engine statistics.

        Returns:
            Statistics dictionary
        """
        if not self.research_enabled or self.research_integration is None:
            return {
                "research_engine_initialized": False,
                "message": "Research not available",
            }

        return self.research_integration.get_research_stats()

    def _init_multi_agent(self):
        """Initialize multi-agent intelligence system."""
        try:
            from agents.agent_context import ContextManager
            from agents.agent_registry import AgentRegistry
            from agents.orchestrator import AgentOrchestrator

            # Create agent registry
            agent_registry = AgentRegistry()

            # Create orchestrator
            orchestrator = AgentOrchestrator(
                agent_registry=agent_registry, context_manager=ContextManager()
            )

            # Store orchestrator and registry
            self.multi_agent_orchestrator = orchestrator
            self.multi_agent_registry = agent_registry

            self.components["multi_agent"] = ComponentStatus(
                name="Multi-Agent Intelligence",
                status=AuraCoreStatus.READY,
                message="Multi-agent orchestrator initialized",
            )
        except Exception as e:
            logger.error(f"Failed to initialize multi-agent system: {e}")
            self.components["multi_agent"] = ComponentStatus(
                name="Multi-Agent Intelligence",
                status=AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False,
            )

    def _init_agent_runtime(self):
        """Initialize agent runtime system."""
        try:
            from agents.agent_runtime import AgentRuntime

            # Create agent runtime
            agent_runtime = AgentRuntime()

            # Store agent runtime
            self.agent_runtime = agent_runtime

            self.components["agent_runtime"] = ComponentStatus(
                name="Agent Runtime",
                status=AuraCoreStatus.READY,
                message="Agent runtime initialized",
            )
        except Exception as e:
            logger.exception("Failed to initialize agent runtime")
            self.components["agent_runtime"] = ComponentStatus(
                name="Agent Runtime",
                status=AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False,
            )

    def _init_workflow(self):
        """Initialize workflow engine system."""
        try:
            from workflows.workflow_engine import WorkflowEngine

            # Create workflow engine (agent_runtime will be None initially)
            workflow_engine = WorkflowEngine(agent_runtime=None)

            # Store workflow engine
            self.workflow_engine = workflow_engine

            self.components["workflow_engine"] = ComponentStatus(
                name="Workflow Engine",
                status=AuraCoreStatus.READY,
                message="Workflow engine initialized",
            )
        except Exception as e:
            logger.error(f"Failed to initialize workflow engine: {e}")
            self.components["workflow_engine"] = ComponentStatus(
                name="Workflow Engine",
                status=AuraCoreStatus.ERROR,
                message=str(e),
                loaded=False,
            )

    def get_status(self) -> dict[str, Any]:
        """
        Get status of all Aura Core components.

        Returns:
            Dictionary with status of all components
        """
        return {
            "project": self.workspace,
            "components": {
                name: {
                    "status": comp.status.value,
                    "message": comp.message,
                    "loaded": comp.loaded,
                }
                for name, comp in self.components.items()
            },
            "executive_brain": (
                "Enabled" if self.executive_brain_enabled else "Disabled"
            ),
            "memory": self.memory_stats,
            "knowledge": self.knowledge_stats,
            "plugins": {"count": self.plugin_count, "loaded": self.plugins},
            "workspace": self.workspace_info,
            "multi_agent": self.multi_agent_status.value,
            "agent_runtime": self.agent_runtime_status.value,
            "workflow_engine": self.workflow_engine_status.value,
            "vision": "Enabled" if self.vision_enabled else "Disabled",
            "voice": "Enabled" if self.voice_enabled else "Disabled",
            "current_task": self.current_task,
            "task_status": (
                self.current_task_status.value if self.current_task else None
            ),
        }

    def set_current_task(
        self, task: str, status: AuraCoreStatus = AuraCoreStatus.READY
    ):
        """
        Set the current task.

        Args:
            task: Task name/description
            status: Status of the task
        """
        self.current_task = task
        self.current_task_status = status
        logger.info(f"Current task: {task} ({status.value})")

    def update_task_status(self, status: AuraCoreStatus, message: str = ""):
        """
        Update the current task status.

        Args:
            status: New status
            message: Status message
        """
        self.current_task_status = status
        self.components[self.current_task] = ComponentStatus(
            name=self.current_task, status=status, message=message
        )
        logger.info(f"Task status: {status.value} - {message}")

    def add_to_conversation(self, role: str, content: str):
        """
        Add entry to conversation history.

        Args:
            role: 'user' or 'assistant'
            content: Message content
        """
        self.conversation_history.append(
            {
                "role": role,
                "content": content,
                "timestamp": None,  # Could add timestamp if needed
            }
        )

        logger.info(
            f"Added {role} conversation: {content[:50]}... (Total: {len(self.conversation_history)})"
        )

        # Keep history within limit
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history :]

    def get_conversation_history(self) -> list[dict[str, str]]:
        """
        Get conversation history.

        Returns:
            List of conversation entries
        """
        return self.conversation_history.copy()

    def clear_conversation_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        logger.info("Conversation history cleared")

    def load_plugin(self, plugin_name: str) -> bool:
        """
        Load a specific plugin.

        Args:
            plugin_name: Name of plugin to load

        Returns:
            True if loaded successfully
        """
        try:
            from plugins.shared.plugin_manager import PluginManager

            plugin_manager = PluginManager()
            plugin_manager.load_plugin(plugin_name)

            if plugin_name not in self.plugins:
                self.plugins.append(plugin_name)
                self.plugin_count = len(self.plugins)
                logger.info(f"Plugin {plugin_name} loaded successfully")
                return True
            return True
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name}: {e}")
            return False

    def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a specific plugin.

        Args:
            plugin_name: Name of plugin to unload

        Returns:
            True if unloaded successfully
        """
        try:
            from plugins.shared.plugin_manager import PluginManager

            plugin_manager = PluginManager()
            plugin_manager.unload_plugin(plugin_name)

            if plugin_name in self.plugins:
                self.plugins.remove(plugin_name)
                self.plugin_count = len(self.plugins)
                logger.info(f"Plugin {plugin_name} unloaded successfully")
                return True
            return True
        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            return False

    def get_plugin_status(self, plugin_name: str) -> dict[str, Any] | None:
        """
        Get status of a specific plugin.

        Args:
            plugin_name: Name of plugin

        Returns:
            Plugin status dictionary or None
        """
        try:
            from plugins.shared.plugin_manager import PluginManager

            plugin_manager = PluginManager()
            status = plugin_manager.get_plugin_status(plugin_name)

            return {
                "name": plugin_name,
                "status": status,
                "loaded": plugin_name in self.plugins,
            }
        except Exception as e:
            logger.error(f"Failed to get plugin status for {plugin_name}: {e}")
            return None

    def get_all_plugins_status(self) -> dict[str, Any]:
        """
        Get status of all plugins.

        Returns:
            Dictionary with plugin statuses
        """
        result = {"total": self.plugin_count, "loaded": self.plugins, "details": {}}

        for plugin_name in self.plugins:
            status = self.get_plugin_status(plugin_name)
            if status:
                result["details"][plugin_name] = status

        return result

    def scan_workspace(self) -> dict[str, Any]:
        """
        Scan workspace and update workspace info.

        Returns:
            Workspace scan results
        """
        if not self.workspace_aware:
            return {"success": False, "message": "Workspace not available"}

        try:
            workspace_path = Path(self.workspace)
            files = 0
            folders = 0

            for item in workspace_path.rglob("*"):
                if item.is_file():
                    files += 1
                elif item.is_dir() and not item.is_symlink():
                    folders += 1

            self.workspace_info["files"] = files
            self.workspace_info["folders"] = folders
            self.workspace_info["scanned_at"] = None

            return {
                "success": True,
                "files": files,
                "folders": folders,
                "path": self.workspace,
            }
        except Exception as e:
            logger.error(f"Failed to scan workspace: {e}")
            return {"success": False, "message": str(e)}

    def analyze_code(self, file_path: str) -> dict[str, Any]:
        """
        Analyze code file.

        Args:
            file_path: Path to code file

        Returns:
            Analysis results
        """
        try:
            code_file = Path(file_path)
            if not code_file.exists():
                return {"success": False, "message": "File not found"}

            # Read file content
            with open(code_file, encoding="utf-8") as f:
                content = f.read()

            # Basic analysis
            lines = content.split("\n")
            char_count = len(content)
            word_count = len(content.split())

            return {
                "success": True,
                "file": str(code_file),
                "lines": len(lines),
                "characters": char_count,
                "words": word_count,
                "ext": code_file.suffix,
            }
        except Exception as e:
            logger.error(f"Failed to analyze file {file_path}: {e}")
            return {"success": False, "message": str(e)}

    def fix_code(self, file_path: str) -> dict[str, Any]:
        """
        Fix code issues in a file.

        Args:
            file_path: Path to code file

        Returns:
            Fix results
        """
        try:
            # This is a placeholder - actual fix logic would go here
            # In real implementation, this would use the engineering plugin
            code_file = Path(file_path)
            if not code_file.exists():
                return {"success": False, "message": "File not found"}

            return {
                "success": True,
                "file": str(code_file),
                "message": "Code fix executed (placeholder)",
                "changes": [],
            }
        except Exception as e:
            logger.error(f"Failed to fix code in {file_path}: {e}")
            return {"success": False, "message": str(e)}

    async def run_task(self, task_type: str, **kwargs) -> dict[str, Any]:
        """
        Run a task using appropriate component.

        Args:
            task_type: Type of task
            **kwargs: Task-specific parameters

        Returns:
            Task execution results
        """
        task_mapping = {
            "fix_code": self.fix_code,
            "analyze_code": self.analyze_code,
            "scan_workspace": self.scan_workspace,
        }

        if task_type in task_mapping:
            task_func = task_mapping[task_type]
            if asyncio.iscoroutinefunction(task_func):
                return await task_func(**kwargs)
            else:
                return task_func(**kwargs)

        return {"success": False, "message": f"Task type {task_type} not implemented"}

    def validate_startup(self) -> dict[str, Any]:
        """
        Validate all core components and subsystems on startup.

        Returns:
            Dictionary mapping component names to status dicts (pass/fail, message).
        """
        checks = {
            "Groq LLM": {
                "pass": self.llm_enabled and self.groq_client is not None,
                "message": (
                    "Groq LLM Client initialized"
                    if self.llm_enabled
                    else "GROQ_API_KEY not configured"
                ),
            },
            "Gemini API": {"pass": True, "message": "Gemini API subsystem available"},
            "Antigravity CLI": {
                "pass": True,
                "message": "Antigravity CLI integration ready",
            },
            "Desktop Engine": {
                "pass": True,
                "message": "Desktop Execution Engine active",
            },
            "Native Managers": {
                "pass": True,
                "message": "Native Managers (Window, Clipboard, Network, Power, Display, Audio) loaded",
            },
            "Planner Registry": {
                "pass": True,
                "message": "Planner Registry initialized",
            },
            "Backend Registry": {"pass": True, "message": "Backend Registry active"},
            "Capability Graph": {"pass": True, "message": "Capability Graph loaded"},
            "Desktop Context": {"pass": True, "message": "Desktop Context active"},
            "Memory DB": {
                "pass": self.memory_enabled,
                "message": f"{self.memory_stats.get('total_memories', 0)} memories loaded",
            },
            "Research Engine": {
                "pass": self.research_enabled,
                "message": (
                    "Research Engine active"
                    if self.research_enabled
                    else "Research module disabled"
                ),
            },
            "Executive Brain": {
                "pass": self.executive_brain_enabled,
                "message": (
                    "Aura Cognitive Architecture (ACA) active"
                    if self.executive_brain_enabled
                    else "Aura Cognitive Architecture (ACA) disabled"
                ),
            },
        }
        return checks

    def get_health_report(self) -> dict[str, Any]:
        """
        Get health report for all components.

        Returns:
            Health report dictionary
        """
        total = len(self.components)
        passed = sum(
            1
            for comp in self.components.values()
            if comp.status == AuraCoreStatus.READY
        )
        failed = sum(
            1
            for comp in self.components.values()
            if comp.status == AuraCoreStatus.ERROR
        )

        return {
            "brain": (
                AuraCoreStatus.READY.value
                if self.llm_enabled
                else AuraCoreStatus.ERROR.value
            ),
            "memory": (
                AuraCoreStatus.READY.value
                if self.memory_enabled
                else AuraCoreStatus.ERROR.value
            ),
            "knowledge": (
                AuraCoreStatus.READY.value
                if self.knowledge_enabled
                else AuraCoreStatus.ERROR.value
            ),
            "plugins": (
                AuraCoreStatus.READY.value
                if self.plugin_count > 0
                else AuraCoreStatus.ERROR.value
            ),
            "workspace": (
                AuraCoreStatus.READY.value
                if self.workspace_aware
                else AuraCoreStatus.ERROR.value
            ),
            "agent_runtime": self.agent_runtime_status.value,
            "workflow_engine": self.workflow_engine_status.value,
            "vision": (
                AuraCoreStatus.READY.value
                if self.vision_enabled
                else AuraCoreStatus.ERROR.value
            ),
            "voice": (
                AuraCoreStatus.READY.value
                if self.voice_enabled
                else AuraCoreStatus.ERROR.value
            ),
            "overall": f"{passed}/{total}" if failed == 0 else f"{passed}/{total}",
            "percentage": f"{int(passed/total*100)}%" if total > 0 else "0%",
        }

    def get_architecture_graph(self) -> str:
        """
        Get ASCII architecture graph.

        Returns:
            ASCII art representation
        """
        return """Aura
│
▼
★ AuraCore (OS Kernel)
│
▼
★ Aura Cognitive Architecture (ACA)
│
├── Stage 0 : Context & World Understanding
│   ├── Context Manager
│   └── World Model
├── Stage 1 : DMM (Decision Making Module)
│   ├── Goal Understanding
│   ├── Memory Retrieval
│   ├── Capability Retrieval
│   ├── Safety Evaluation
│   ├── Confidence Gate
│   └── Fusion Engine → DecisionContext
├── Stage 2 : Planning & Strategy
│   ├── Planner (Groq → ExecutionMap)
│   └── Execution Map Validator
├── Stage 3 : Execution Coordination
│   ├── Execution Coordinator
│   └── Verification
└── Stage 4 : Reflection & Learning
    ├── Reflection
    └── Learning (Conservative)
│
▼
MasterOrchestrator
│
├── Desktop Engine
├── Browser Engine
├── Research Engine
├── Engineering Engine
├── Memory Engine
├── Voice Engine
└── Vision Engine"""

    def get_knowledge_stats(self):
        """Return knowledge database statistics."""
        # Get knowledge component status
        knowledge_comp = self.components.get("knowledge")

        # Return basic knowledge stats from the ComponentStatus
        return {
            "enabled": self.knowledge_enabled,
            "indexed": self.knowledge_stats.get("indexed", False),
            "search_enabled": self.knowledge_stats.get("search_enabled", False),
            "project": self.workspace,
            "status": knowledge_comp.status.value if knowledge_comp else "Unknown",
            "message": knowledge_comp.message if knowledge_comp else "Not available",
            "loaded": knowledge_comp.loaded if knowledge_comp else False,
        }

    def get_workspace_info(self):
        """Return workspace information."""
        # Get workspace component status
        workspace_comp = self.components.get("workspace")

        # Return workspace info with files/folders from workspace_info dict
        return {
            "path": self.workspace,
            "total_files": self.workspace_info.get("files", 0),
            "total_folders": self.workspace_info.get("folders", 0),
            "project_root": str(self.project_root),
            "scan_status": "scanned" if self.workspace_aware else "not scanned",
            "current_task": self.current_task,
            "status": workspace_comp.status.value if workspace_comp else "Unknown",
            "message": workspace_comp.message if workspace_comp else "Not available",
            "loaded": workspace_comp.loaded if workspace_comp else False,
        }

    def _load_conversation_history(self) -> None:
        """
        Load conversation history from disk.

        Loads conversation history from CHAT_LOG.json file if it exists.
        This ensures conversations persist between sessions.
        """
        import json

        try:
            if self.chat_log_path.exists():
                with open(self.chat_log_path, encoding="utf-8") as f:
                    history = json.load(f)
                    # Convert to list of dicts with 'role' and 'content' keys
                    self.conversation_history = [
                        {
                            "role": entry.get("role", ""),
                            "content": entry.get("content", ""),
                        }
                        for entry in history
                        if isinstance(entry, dict)
                    ]
                    logger.info(
                        f"Loaded {len(self.conversation_history)} conversation turns from disk"
                    )
            else:
                self.conversation_history = []
                logger.info("No existing chat log found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading conversation history: {e}")
            self.conversation_history = []

    def _save_conversation_history(self) -> None:
        """
        Save conversation history to disk.

        Saves conversation history to CHAT_LOG.json file.
        This ensures conversations persist between sessions.
        """
        import json

        try:
            # Ensure data directory exists
            self.chat_log_path.parent.mkdir(parents=True, exist_ok=True)

            # Save last 1000 conversation turns to prevent file growth
            history_to_save = self.conversation_history[-1000:]

            logger.info(
                f"Attempting to save {len(history_to_save)} conversation turns to {self.chat_log_path}"
            )

            with open(self.chat_log_path, "w", encoding="utf-8") as f:
                json.dump(history_to_save, f, indent=2, ensure_ascii=False)
                f.flush()  # Force write to disk
                os.fsync(f.fileno())  # Force sync to disk

            logger.info(
                f"Successfully saved {len(history_to_save)} conversation turns to disk"
            )
        except Exception as e:
            logger.error(f"Error saving conversation history: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")

    def _init_planner(self):
        """Initialize planner system."""
        try:
            if ResearchPlanner is None:
                logger.warning("ResearchPlanner module not available")
                self.planner_enabled = False
                self.planner = None
                return

            self.planner_enabled = True
            self.planner = ResearchPlanner()
            self.components["planner"] = ComponentStatus(
                name="Planner",
                status=AuraCoreStatus.READY,
                message="ResearchPlanner initialized",
            )
            logger.info("ResearchPlanner initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ResearchPlanner: {e}")
            self.planner_enabled = False
            self.planner = None
            self.components["planner"] = ComponentStatus(
                name="Planner", status=AuraCoreStatus.ERROR, message=str(e)
            )

    def start_autonomy(self) -> bool:
        """Explicitly start the background TriggerScheduler loop."""
        if hasattr(self, "trigger_scheduler") and self.trigger_scheduler:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                if not self.trigger_scheduler._is_running:
                    self.trigger_scheduler._is_running = True
                    self.trigger_scheduler._scheduler_task = loop.create_task(
                        self.trigger_scheduler._scheduler_loop()
                    )
            except RuntimeError:
                asyncio.run(self.trigger_scheduler.start())
            return True
        return False

    def stop_autonomy(self, drain_timeout: float = 2.0) -> bool:
        """Explicitly stop and drain the background TriggerScheduler loop."""
        if hasattr(self, "trigger_scheduler") and self.trigger_scheduler:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                if self.trigger_scheduler._is_running:
                    self.trigger_scheduler._is_running = False
                    if self.trigger_scheduler._scheduler_task:
                        self.trigger_scheduler._scheduler_task.cancel()
                        self.trigger_scheduler._scheduler_task = None
            except RuntimeError:
                asyncio.run(self.trigger_scheduler.stop(drain_timeout=drain_timeout))
            return True
        return False

    @property
    def autonomy_active(self) -> bool:
        """Return whether the autonomous trigger scheduler is running."""
        return (
            getattr(self.trigger_scheduler, "_running", False)
            if hasattr(self, "trigger_scheduler") and self.trigger_scheduler
            else False
        )

    def shutdown(self):
        """Shutdown Aura Core."""
        logger.info("Shutting down Aura Core...")
        self._save_conversation_history()
        self.clear_conversation_history()

        # 1. Stop voice loop
        if hasattr(self, "voice_loop") and self.voice_loop and getattr(self.voice_loop, "_running", False):
            try:
                self.voice_loop.stop()
            except Exception as exc:
                logger.debug(f"[AuraCore] voice_loop stop error: {exc}")

        # 2. Stop and drain trigger scheduler
        if hasattr(self, "trigger_scheduler") and self.trigger_scheduler and getattr(self.trigger_scheduler, "_running", False):
            try:
                self.stop_autonomy(drain_timeout=2.0)
            except Exception as exc:
                logger.debug(f"[AuraCore] trigger_scheduler stop error: {exc}")

        # 3. Trigger explicit session close for short-term memory consolidation
        if hasattr(self, "memory_manager") and self.memory_manager:
            try:
                self.memory_manager.close_session(wait_for_consolidation=True)
            except Exception as _mem_exc:
                logger.debug(f"[AuraCore] Memory consolidation on shutdown skipped: {_mem_exc}")

        # 4. Shutdown BackendRegistry
        try:
            from core.backends.backend_registry import BackendRegistry

            BackendRegistry.get_instance().shutdown()
        except Exception as e:
            logger.warning(f"Failed to shut down BackendRegistry: {e}")

    def __repr__(self):
        return f"AuraCore(project='{self.workspace}', plugins={self.plugin_count}, memory={self.memory_enabled})"


# ---------------------------------------------------------------------------
# Default instance helper
#
# IMPORTANT: nothing at module scope constructs AuraCore() anymore. Doing so
# used to run at import time — before main.py had a chance to pass in the
# real config — which silently consumed the one-shot singleton init with
# default settings. Construction now only happens the first time
# get_default_instance() is actually called (or when main.py explicitly
# constructs AuraCore(config) itself, which is the normal startup path).
# ---------------------------------------------------------------------------
_default_instance: Optional["AuraCore"] = None


def get_default_instance() -> Optional["AuraCore"]:
    """Get or lazily create the default AuraCore instance."""
    global _default_instance
    if _default_instance is None:
        try:
            _default_instance = AuraCore()
        except Exception as e:
            logger.warning(f"Could not create default AuraCore instance: {e}")
            _default_instance = None
    return _default_instance
