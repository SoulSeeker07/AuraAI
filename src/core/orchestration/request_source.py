"""
RequestSource — Request Origin Classification
Location: src/core/orchestration/request_source.py

Identifies the initiating context of a MasterOrchestrator request.
Used by ExecutionPolicy to select the appropriate autonomy floor
and by SecurityAuditLogger to distinguish human-visible from
fully-autonomous actions in the audit ledger.
"""

from __future__ import annotations

from enum import Enum


class RequestSource(str, Enum):
    """
    Identifies who or what initiated a MasterOrchestrator request.

    Gating model (as currently implemented in process_request_async):
        HUMAN_INTERACTIVE  → skip_confirmation_intercept=False (ASK_USER prompts are live)
        TRIGGER_AUTONOMOUS → skip_confirmation_intercept=True  (no ASK_USER; HIGH-risk
                             actions route to CryptographicApprovalAuthority HMAC gate
                             and suspend the DAG for human resumption via ticket)
        DAEMON_BACKGROUND  → same as TRIGGER_AUTONOMOUS

    NOTE — NOT YET IMPLEMENTED: The _autonomy_level_ctx ContextVar in ExecutionPolicy
    is the intended future home for request-scoped AutonomyLevel escalation
    (HUMAN_INTERACTIVE → ASSISTED, TRIGGER_AUTONOMOUS/DAEMON_BACKGROUND → AUTONOMOUS).
    That wiring does not exist yet. _autonomy_level_ctx is never set in any production
    code path; it always reads its default (AutonomyLevel.ASSISTED). Do not build on the
    assumption that source type changes the ExecutionPolicy autonomy level — it does not.
    See backlog: "Wire RequestSource → AutonomyLevel escalation through autonomy_scope()."

    Hard-blocking: AutonomyGovernanceEngine.PROHIBITED capabilities remain
    unconditionally blocked regardless of source, token, or autonomy level.
    trigger_allowed_domains enforces an additional domain ceiling for
    TRIGGER_AUTONOMOUS requests.
    """

    HUMAN_INTERACTIVE = "human_interactive"
    """Direct user turn — CLI, GUI, voice, or API with a human in the loop."""

    TRIGGER_AUTONOMOUS = "trigger_autonomous"
    """Fired by TriggerScheduler. No human is present in the request loop."""

    DAEMON_BACKGROUND = "daemon_background"
    """Spawned by DaemonRuntime for a background job. No interactive session."""

    AGENT_DELEGATED = "agent_delegated"
    """Delegated to a subagent / worker task; inherits parent context autonomy floor."""


__all__ = ["RequestSource"]
