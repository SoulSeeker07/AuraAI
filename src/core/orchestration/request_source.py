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

    Autonomy floor mapping (enforced in process_request_async):
        HUMAN_INTERACTIVE  → AutonomyLevel.ASSISTED  (default; HIGH-risk → ASK_USER)
        TRIGGER_AUTONOMOUS → AutonomyLevel.AUTONOMOUS (HIGH-risk → HMAC gate, never ASK_USER)
        DAEMON_BACKGROUND  → AutonomyLevel.AUTONOMOUS (same as TRIGGER_AUTONOMOUS)

    Note: AutonomyLevel.AUTONOMOUS is a *floor*, not a ceiling.
    AutonomyGovernanceEngine.PROHIBITED capabilities remain unconditionally
    hard-blocked regardless of source or token. trigger_allowed_domains
    enforces an additional domain ceiling for TRIGGER_AUTONOMOUS requests.
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
