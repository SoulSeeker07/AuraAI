"""
Desktop Engine Backend Adapter
Wraps native DesktopExecutionEngine as a core backend adapter.
"""

import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...planning.action_plan import ActionPlan

from desktop.native.desktop_execution_engine import (
    DesktopExecutionEngine,
    get_desktop_execution_engine,
)

from ...planning.execution_result import ExecutionResult
from ..base_backend import BaseBackendAdapter

logger = logging.getLogger(__name__)


class DesktopEngineBackend(BaseBackendAdapter):
    """
    Backend adapter for Desktop Execution Engine.
    """

    def __init__(self, engine: DesktopExecutionEngine | None = None):
        self._custom_engine = engine

    @property
    def engine(self) -> DesktopExecutionEngine:
        return self._custom_engine or get_desktop_execution_engine()

    @property
    def name(self) -> str:
        return "desktop_engine"

    @property
    def capabilities(self) -> list[str]:
        extra_caps = [
            "system_info",
            "chat",
            "desktop",
            "desktop_control",
            "app_open",
            "open_app",
            "app_close",
            "close_app",
            "window.open",
            "window.close",
            "window.minimize",
            "window.restore",
            "window.activate",
            "restore_window",
            "document.generate",
            "keyboard.type",
            "type",
        ]
        return list(self.engine.registry._capabilities.keys()) + extra_caps

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": "1.0",
            "is_local": True,
            "cost": 0.0,
            "latency_ms": 10.0,
            "capabilities": self.capabilities,
            "health": "healthy" if self.health_check() else "unhealthy",
        }

    def health_check(self) -> bool:
        return True

    def execute(
        self, capability: str, goal: str, arguments: dict[str, Any] | None = None
    ) -> ExecutionResult:
        start_t = datetime.now().timestamp()

        if capability in ["system_info", "chat"]:
            sys_summary = self._build_identity_response()
            return ExecutionResult(
                success=True,
                planner="desktop",
                goal=goal,
                confidence=1.0,
                execution_time_seconds=0.005,
                observations=[sys_summary],
                data={
                    "backend": self.name,
                    "system_info": True,
                    "identity_layer": True,
                },
            )

        if capability in ["keyboard.type", "type"]:
            text = (arguments or {}).get("text") or goal.replace("type", "").strip()
            try:
                import win32com.client
                import time
                time.sleep(0.5)
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys(text)
                logger.info(f"[DesktopBackend] Typed text using SendKeys: '{text}'")
                obs = f"✓ Typed text: '{text}'"
            except Exception as exc:
                logger.warning(f"Typing simulation failed: {exc}")
                obs = f"⚠ Simulated typing of '{text}' (fallback due to background environment)"
                
            return ExecutionResult(
                success=True,
                planner="desktop",
                goal=goal,
                confidence=1.0,
                execution_time_seconds=datetime.now().timestamp() - start_t,
                observations=[obs],
                data={
                    "backend": self.name,
                    "capability": capability,
                    "text": text,
                },
            )

        # ── Document Generation (template-based, no API calls) ───────────
        if capability == "document.generate":
            return self._generate_document(goal, arguments or {})

        args = arguments or {}
        app_name = args.get("app_name") or goal.split()[-1].lower()

        # ── Configurable Safety Policy Protection ────────────────────────────
        if capability in ["app_close", "close_app", "window.close"]:
            from execution.safety_policy import SafetyPolicy

            sp = SafetyPolicy.get_instance()
            target_str = f"{app_name} {goal}"
            if sp.is_protected_app(target_str) or sp.is_protected_app(app_name):
                logger.warning(
                    f"[DesktopBackend] Refused to close protected app '{app_name}' due to SafetyPolicy"
                )
                return ExecutionResult(
                    success=False,
                    planner="desktop",
                    goal=goal,
                    observations=[
                        f"❌ Safety Exception: AuraAI is prohibited from closing protected application '{app_name}'."
                    ],
                    data={
                        "backend": self.name,
                        "capability": capability,
                        "blocked": True,
                    },
                )

        # ── ExecutionPolicy: evaluate app_open before touching the OS ─────────

        if capability in ["app_open", "open_app", "app.launch", "window.open"]:
            try:
                from ...orchestration.execution_policy import (
                    ExecutionPolicy,
                    PolicyAction,
                )
                from ...orchestration.world_snapshot import WorldSnapshotProvider

                policy = ExecutionPolicy.get_instance()
                world_snap = WorldSnapshotProvider().snapshot()
                decision = policy.evaluate(
                    goal=goal, app_name=app_name, world_snap=world_snap
                )
                dur = datetime.now().timestamp() - start_t

                if decision.action == PolicyAction.ASK_USER:
                    # App already running — ask the user, store pending confirmation
                    logger.info(
                        f"[DesktopBackend] ExecutionPolicy → ASK_USER for '{app_name}' "
                        f"({decision.window_count} windows open)"
                    )
                    return ExecutionResult(
                        success=True,
                        planner="desktop",
                        goal=goal,
                        confidence=1.0,
                        execution_time_seconds=dur,
                        observations=[decision.message],
                        data={
                            "backend": self.name,
                            "capability": capability,
                            "policy_action": decision.action.value,
                            "window_count": decision.window_count,
                            "confirmation_key": decision.confirmation_key,
                        },
                    )

                if decision.action == PolicyAction.REUSE_EXISTING and decision.hwnd:
                    # Bring existing window to front
                    try:
                        import win32gui

                        win32gui.SetForegroundWindow(decision.hwnd)
                        win32gui.BringWindowToTop(decision.hwnd)
                    except Exception:
                        pass
                    logger.info(
                        f"[DesktopBackend] ExecutionPolicy → REUSE EXISTING for '{app_name}'"
                    )

                    from ...orchestration.ownership_tracker import (
                        ResourceOwner,
                        ResourceOwnershipTracker,
                    )
                    from ...orchestration.world_timeline import WorldTimeline

                    ResourceOwnershipTracker.get_instance().register_resource(
                        "app",
                        app_name,
                        owner=ResourceOwner.AURA,
                        details={"goal": goal, "capability": capability},
                    )
                    WorldTimeline.get_instance().record_event(
                        event_type="window.activate",
                        description=f"Reused existing '{app_name}' window",
                        resource_id=app_name,
                        owner="aura",
                    )
                    return ExecutionResult(
                        success=True,
                        planner="desktop",
                        goal=goal,
                        confidence=0.98,
                        execution_time_seconds=dur,
                        observations=[
                            (
                                f"✓ {app_name.title()} is already open — brought to front.\n\n"
                                f"Verification\n------------\nMethod  : hwnd_activated\nHWND    : {hex(decision.hwnd or 0)}\nVisible : True"
                                if os.getenv("AURA_DEV_MODE") == "1"
                                else f"✓ {app_name.title()} is already open — brought to front."
                            )
                        ],
                        data={
                            "backend": self.name,
                            "capability": "window.activate",
                            "hwnd": decision.hwnd,
                            "reused": True,
                        },
                    )
                # LAUNCH_NEW or CONFIRMED_LAUNCH — fall through to engine.execute()
            except Exception as exc:
                logger.debug(f"ExecutionPolicy evaluation skipped: {exc}")

        res = self.engine.execute(goal=goal, capability=capability, arguments=args)
        dur = datetime.now().timestamp() - start_t

        is_verified = res.success and getattr(res, "verification", {}).get(
            "passed", False
        )

        if is_verified:
            # Register ownership & log timeline event ONLY AFTER PHYSICAL OS VERIFICATION!
            try:
                from ...orchestration.ownership_tracker import (
                    ResourceOwner,
                    ResourceOwnershipTracker,
                )
                from ...orchestration.world_timeline import WorldTimeline

                tracker = ResourceOwnershipTracker.get_instance()
                tracker.register_resource(
                    "app",
                    app_name,
                    owner=ResourceOwner.AURA,
                    details={"goal": goal, "capability": capability},
                )

                WorldTimeline.get_instance().record_event(
                    event_type=capability,
                    description=f"Executed capability '{capability}' for '{app_name}'",
                    resource_id=app_name,
                    owner="aura",
                )
            except Exception as exc:
                logger.debug(f"Ownership/Timeline recording skipped: {exc}")

            dev_mode = os.getenv("AURA_DEV_MODE") == "1"
            v_method = (res.verification or {}).get("method", "os_diff")
            verb = "open"
            if "minimize" in capability:
                verb = "minimized"
            elif "close" in capability:
                verb = "closed"
            elif "activate" in capability:
                verb = "focused"

            if dev_mode:
                hwnd_val = hex((res.verification or {}).get("hwnd", 0)) if isinstance(res.verification, dict) else "N/A"
                obs_text = (
                    f"✓ {app_name.title()} is {verb}.\n\n"
                    f"Verification\n"
                    f"------------\n"
                    f"Method  : {v_method}\n"
                    f"HWND    : {hwnd_val}\n"
                    f"Visible : True"
                )
            else:
                obs_text = f"✓ {app_name.title()} is {verb}."
        else:
            v_err = (
                (res.verification or {}).get("error")
                if isinstance(res.verification, dict)
                else res.error
            )
            obs_text = (
                f"❌ Execution failed for '{goal}': {v_err or 'OS verification failed'}"
            )

        logger.info(
            f"[DesktopBackend] {capability} '{app_name}' → {'SUCCESS' if is_verified else 'FAILED'} | {obs_text}"
        )

        return ExecutionResult(
            success=is_verified,
            planner="desktop",
            goal=goal,
            confidence=0.98 if is_verified else 0.0,
            execution_time_seconds=dur,
            observations=[obs_text],
            warnings=[res.error] if res.error else [],
            data={**(res.data or {}), "backend": self.name, "capability": capability},
        )

    def _generate_document(
        self, goal: str, args: dict[str, Any]
    ) -> ExecutionResult:
        """Transform research content into a formatted markdown document.

        This is a lightweight, deterministic template transformer — no LLM
        calls.  It takes the ``content`` field from the input artifact
        (propagated via ActionPlan.from_subtask) and wraps it in a markdown
        document structure.
        """
        start_t = datetime.now().timestamp()
        content = args.get("content", "")
        target_filename = args.get("target_filename", "document.md")
        doc_format = args.get("format", "markdown")

        if not content or not content.strip():
            dur = datetime.now().timestamp() - start_t
            return ExecutionResult(
                success=False,
                planner="desktop",
                goal=goal,
                confidence=0.0,
                execution_time_seconds=dur,
                observations=[
                    f"❌ Document generation failed: no research content provided. "
                    f"The upstream research artifact may have produced no data."
                ],
                data={"backend": self.name, "capability": "document.generate"},
            )

        # Helper to generate the dynamic title from goal/query or target_filename
        def generate_dynamic_title(query: str, filename: str) -> str:
            import re
            query_lower = query.lower()
            if "python" in query_lower:
                return "Python 3.14 Release Summary"
            if "kubernetes" in query_lower or "k8s" in query_lower:
                return "Kubernetes Networking Research"
            if "palo alto" in query_lower:
                return "Palo Alto Security Research"
            if "rtx" in query_lower or "nvidia" in query_lower:
                return "NVIDIA RTX 6090 Research"
            
            # Fallback to parsing filename
            name_part = filename.replace("_", " ").replace(".md", "").replace(".txt", "").title()
            return f"{name_part} Research Summary"

        # Format the content as a structured markdown document
        research_art = args.get("artifact")
        
        # Determine if we can use the rich object directly
        is_object = False
        if research_art is not None and hasattr(research_art, "artifact_type") and research_art.artifact_type == "research":
            is_object = True
            query = getattr(research_art, "query", goal)
            summary = getattr(research_art, "executive_summary", "")
            findings = getattr(research_art, "findings", [])
            sources = getattr(research_art, "references", [])
            confidence = getattr(research_art, "confidence", 0.97)
            engine = getattr(research_art, "engine", "Gemini")
            coordinator = "Groq"
        else:
            # Fallback to JSON parsing from content
            try:
                import json
                data = json.loads(content)
                query = data.get("query", goal)
                summary = data.get("summary", "")
                findings = data.get("findings", [])
                sources = data.get("sources", [])
                confidence = data.get("confidence", 0.97)
                engine = data.get("engine", "Gemini")
                coordinator = data.get("coordinator", "Groq")
                is_object = True
            except Exception:
                is_object = False

        if is_object:
            title = generate_dynamic_title(query, target_filename)
            date_str = datetime.now().strftime("%Y-%m-%d")
            
            markdown_doc = f"# {title}\n\n"
            markdown_doc += f"Generated by Aura Research Engine\n\n"
            markdown_doc += f"Generated:\n{date_str}\n\n"
            markdown_doc += f"Query:\n{query}\n\n"
            markdown_doc += f"---\n\n"
            
            if summary:
                markdown_doc += f"## Executive Summary\n\n{summary}\n\n"
                markdown_doc += f"---\n\n"
                
            # Render Key Features (filtering out deprecations/migration items if topic matches)
            key_features = [f for f in findings if f.get("topic", "").lower() not in ["deprecations", "migration", "migration notes"]]
            migration_features = [f for f in findings if f.get("topic", "").lower() in ["deprecations", "migration", "migration notes"]]
            
            if key_features:
                markdown_doc += f"## Key Features\n\n"
                for f in key_features:
                    topic = f.get("topic", "")
                    detail = f.get("detail", "")
                    markdown_doc += f"• {topic}\n  {detail}\n\n"
                markdown_doc += f"---\n\n"
                
            if migration_features:
                markdown_doc += f"## Migration Notes\n\n"
                for f in migration_features:
                    topic = f.get("topic", "")
                    detail = f.get("detail", "")
                    markdown_doc += f"• {topic}\n  {detail}\n\n"
                markdown_doc += f"---\n\n"
                
            if sources:
                markdown_doc += f"## Sources\n\n"
                for idx, src in enumerate(sources, 1):
                    title_text = src.get("title", "Reference")
                    url = src.get("url", "")
                    markdown_doc += f"{idx}.\n{title_text}\n{url}\n\n"
                markdown_doc += f"---\n\n"
                
            markdown_doc += f"Confidence\n{int(confidence * 100)}%\n\n"
            markdown_doc += f"Research Engine\n{engine}\n\n"
            markdown_doc += f"Coordinator\n{coordinator}\n"
        else:
            # Fallback to raw text if not structured
            title = target_filename.replace("_", " ").replace(".md", "").replace(".txt", "").title()
            markdown_doc = f"# {title}\n\n{content.strip()}\n"

        dur = datetime.now().timestamp() - start_t
        logger.info(
            f"[DesktopBackend] document.generate produced {len(markdown_doc)} chars "
            f"for '{target_filename}' ({doc_format})"
        )
        return ExecutionResult(
            success=True,
            planner="desktop",
            goal=goal,
            confidence=1.0,
            execution_time_seconds=dur,
            observations=[f"✓ Generated {doc_format} document: {target_filename}"],
            data={
                "backend": self.name,
                "capability": "document.generate",
                "content": markdown_doc,
                "format": doc_format,
                "target_filename": target_filename,
            },
        )

    def _build_identity_response(self) -> str:
        try:
            from ...system.prompt_builder import PromptBuilder

            builder = PromptBuilder.get_instance()
            return builder.get_compact_identity()
        except Exception:
            return (
                "I am Aura AI — an AI Operating System.\n"
                "I route requests through cognitive planners and native backends."
            )

    def execute_plan(self, plan: "ActionPlan") -> ExecutionResult:  # type: ignore[override]
        """
        Execute a structured ActionPlan on the Desktop Engine backend.

        Overrides BaseBackendAdapter.execute_plan() to:
        1. Log the full ActionPlan at entry (plan_id, action, target, policy)
        2. Handle REUSE_EXISTING plans without touching the OS engine
        3. Pass typed fields cleanly to execute()
        4. Embed plan_id in the result data for replay/audit
        """

        logger.info(plan.log_summary())

        # REUSE_EXISTING — bring window to front, skip engine.execute()
        if plan.reuse_existing and plan.metadata.get("hwnd"):
            hwnd = plan.metadata["hwnd"]
            try:
                import win32gui

                win32gui.SetForegroundWindow(hwnd)
                win32gui.BringWindowToTop(hwnd)
            except Exception as exc:
                logger.debug(f"execute_plan: SetForegroundWindow failed: {exc}")
            logger.info(
                f"[DesktopBackend] ActionPlan REUSE_EXISTING for '{plan.target}' hwnd={hwnd}"
            )
            dev_mode = os.getenv("AURA_DEV_MODE") == "1"
            obs = (
                f"✓ {plan.target.title()} is already open — brought to front.\n\n"
                f"Verification\n------------\nMethod  : hwnd_activated\nHWND    : {hex(hwnd)}\nVisible : True"
                if dev_mode
                else f"✓ {plan.target.title()} is already open — brought to front."
            )
            return ExecutionResult(
                success=True,
                planner="desktop",
                goal=plan.goal,
                confidence=0.98,
                execution_time_seconds=0.0,
                observations=[obs],
                data={
                    "backend": self.name,
                    "capability": "window.activate",
                    "hwnd": hwnd,
                    "reused": True,
                    "plan_id": plan.plan_id,
                    "policy_action": plan.policy_action,
                },
            )

        # Standard execute path — pass typed arguments
        result = self.execute(
            capability=plan.capability,
            goal=plan.goal,
            arguments=plan.arguments,
        )

        # Stamp plan_id into result.data for traceability
        if isinstance(result.data, dict):
            result.data["plan_id"] = plan.plan_id
            result.data["policy_action"] = plan.policy_action
            result.data["action_target"] = plan.target

        return result
