"""
Desktop Engine Backend Adapter
Wraps native DesktopExecutionEngine as a core backend adapter.
"""

import logging
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
        self.engine = engine or get_desktop_execution_engine()

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
            "window.activate",
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
                            f"✓ {app_name.title()} is already open — brought to front. (Verified: hwnd_activated)"
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

            v_method = (res.verification or {}).get("method", "os_diff")
            verb = "open"
            if "minimize" in capability:
                verb = "minimized"
            elif "close" in capability:
                verb = "closed"
            elif "activate" in capability:
                verb = "focused"

            obs_text = f"✓ {app_name.title()} is {verb}. (Verified: {v_method})"
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
            return ExecutionResult(
                success=True,
                planner="desktop",
                goal=plan.goal,
                confidence=0.98,
                execution_time_seconds=0.0,
                observations=[
                    f"✓ {plan.target.title()} is already open — brought to front. (Verified: hwnd_activated)"
                ],
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
