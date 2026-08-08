"""
Layer 4: Reflection Engine
==========================

Reflection begins after execution.

Questions include:
    Did execution succeed?
    Did verification pass?
    Did an error occur?
    Can the problem be recovered automatically?
    Should another capability be used?
    Should the user be informed?

Reflection improves robustness without changing the original goal.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .executor import PlanResult, StepResult

logger = logging.getLogger(__name__)


@dataclass
class ReflectionOutcome:
    """The result of reflecting on an execution."""

    success: bool
    reflections: list[str] = field(default_factory=list)
    recoveries: list[str] = field(default_factory=list)
    needs_user_info: bool = False
    user_message: str = ""
    recovered: bool = False
    fallback_actions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "reflections": self.reflections,
            "recoveries": self.recoveries,
            "needs_user_info": self.needs_user_info,
            "user_message": self.user_message,
            "recovered": self.recovered,
            "fallback_actions": self.fallback_actions,
        }


# ── Known Recovery Patterns ─────────────────────────────────────────────────
# Deterministic reflection rules: when a specific error is seen,
# a specific recovery action is applied — without changing the goal.

_RECOVERY_PATTERNS: list[dict[str, Any]] = [
    {
        "error_patterns": [
            "paint.exe",
            "not found",
            "not recognised",
            "path not found",
        ],
        "app_aliases": {"paint": "mspaint"},
        "action": "retry_with_alias",
        "description": "Application not found — try alternate executable name",
    },
    {
        "error_patterns": ["timeout", "timed out"],
        "max_retries": 2,
        "action": "retry_with_longer_timeout",
        "description": "Operation timed out — retry with longer timeout",
    },
    {
        "error_patterns": ["permission denied", "access denied", "unauthorized"],
        "action": "inform_user",
        "description": "Permission denied — inform user and suggest elevated access",
        "needs_user": True,
    },
    {
        "error_patterns": ["connection", "network", "offline", "no internet"],
        "action": "retry_local",
        "description": "Network issue — retry with fallback to local execution",
    },
]


class ReflectionEngine:
    """
    Validates execution results, applies recovery patterns, and
    decides whether the user should be informed.
    """

    def __init__(self):
        self._recovery_patterns = _RECOVERY_PATTERNS

    # ── Public API ──────────────────────────────────────────────────────────

    def reflect(self, plan_result: PlanResult) -> ReflectionOutcome:
        """
        Reflect on the result of an execution plan.

        Args:
            plan_result: The PlanResult from the Executor.

        Returns:
            ReflectionOutcome with recovery attempts and user feedback.
        """
        reflections: list[str] = []
        recoveries: list[str] = []
        fallback_actions: list[dict[str, Any]] = []

        # 1. Did the execution succeed?
        if plan_result.success:
            reflections.append(
                f"Execution succeeded: all {len(plan_result.step_results)} steps passed."
            )
            return ReflectionOutcome(
                success=True,
                reflections=reflections,
                recovered=False,
            )

        reflections.append(
            f"Execution partially failed: {len(plan_result.failed_steps)}/"
            f"{len(plan_result.step_results)} steps failed."
        )

        # 2. Analyze each failed step for recovery
        for failed_step in plan_result.failed_steps:
            reflections.append(
                f"Step {failed_step.action_id} failed: {failed_step.error}"
            )

            # 2a. Can the problem be recovered automatically?
            recovery = self._find_recovery(failed_step)
            if recovery:
                recoveries.append(
                    f"[{failed_step.action_id}] {recovery['description']}"
                )
                fallback_actions.append(
                    {
                        "action_id": failed_step.action_id,
                        "recovery": recovery["action"],
                        "description": recovery["description"],
                    }
                )

                # Log recovery
                logger.info(
                    f"Reflection: Recovery pattern applied for "
                    f"{failed_step.action_id}: {recovery['description']}"
                )

        # 3. Should the user be informed?
        needs_user = (
            any(r.get("needs_user", False) for r in fallback_actions)
            or len(fallback_actions) == 0
        )

        user_message = ""
        if needs_user:
            if fallback_actions:
                user_message = (
                    "Some steps encountered issues that could not be fully "
                    "recovered automatically. "
                    + " ".join(r["description"] for r in fallback_actions)
                )
            else:
                user_message = (
                    "The execution failed without available automatic recovery. "
                    "Please check the errors and try again."
                )

        recovered = len(fallback_actions) > 0

        logger.info(
            f"Reflection complete: recovered={recovered}, "
            f"needs_user_info={needs_user}"
        )

        return ReflectionOutcome(
            success=False,
            reflections=reflections,
            recoveries=recoveries,
            needs_user_info=needs_user,
            user_message=user_message,
            recovered=recovered,
            fallback_actions=fallback_actions,
        )

    # ── Internal Helpers ────────────────────────────────────────────────────

    def _find_recovery(self, step_result: StepResult) -> dict[str, Any] | None:
        """
        Find a recovery pattern matching the error.

        Returns:
            Recovery dict with 'action' and 'description' or None.
        """
        error_lower = (step_result.error or "").lower()

        for pattern in self._recovery_patterns:
            if any(p in error_lower for p in pattern.get("error_patterns", [])):
                # Build the recovery action
                action = pattern.get("action", "retry")
                description = pattern.get("description", "Automatic recovery applied")

                # Check for app alias substitution
                if "app_aliases" in pattern:
                    # Extract the app name from the action parameters
                    app_name = step_result.data.get("app_name", "")
                    if app_name in pattern["app_aliases"]:
                        alias = pattern["app_aliases"][app_name]
                        return {
                            "action": action,
                            "description": description,
                            "needs_user": pattern.get("needs_user", False),
                            "alias": alias,
                        }

                return {
                    "action": action,
                    "description": description,
                    "needs_user": pattern.get("needs_user", False),
                }

        return None


__all__ = ["ReflectionEngine", "ReflectionOutcome"]
