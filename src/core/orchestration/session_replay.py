"""
Session Replay & Explanation Engine
Location: src/core/orchestration/session_replay.py

Provides 100% explainability for AgentSession trajectories:
reconstructs decision traces, policy applications, resource protection choices,
and execution timelines into human-readable explanations.
"""

from __future__ import annotations

import logging
from typing import Any

from .agent_session import AgentSession
from .ownership_tracker import ResourceOwner, ResourceOwnershipTracker
from .world_timeline import WorldTimeline

logger = logging.getLogger(__name__)


class SessionReplay:
    """
    Reconstructs and explains AgentSession execution trajectories.
    """

    @classmethod
    def explain_session(cls, session: AgentSession) -> str:
        """
        Generate a human-readable explanation of why Aura executed a session the way it did.
        """
        lines = [f"Session Replay & Explanation [{session.session_id}]:"]
        lines.append(f"• Goal: '{session.goal}'")
        lines.append(f"• Created At: {session.created_at}")

        if session.decision_trace:
            dt = session.decision_trace
            lines.append("\nExecutive Decision & Reasoning:")
            lines.append(f"  - Policy Applied: {getattr(dt, 'policy_applied', 'Standard Policy')}")
            lines.append(f"  - Chosen Planner: {getattr(dt, 'chosen_planner', 'default')}")
            lines.append(f"  - Chosen Backend: {getattr(dt, 'chosen_backend', 'default')}")
            lines.append(f"  - Confidence: {getattr(dt, 'confidence', 1.0) * 100:.0f}%")
            lines.append("  - Reasoning Steps:")
            steps = getattr(dt, "reasoning_steps", [])
            for step in steps:
                lines.append(f"    * {step}")

        if session.observations:
            lines.append(f"\nObservations Collected ({len(session.observations)}):")
            for obs in session.observations[:5]:
                lines.append(f"  - [{obs.source}] {obs.content[:80]}")

        # Add recent timeline events for this session
        timeline = WorldTimeline.get_instance().get_recent_events(session_id=session.session_id)
        if timeline:
            lines.append(f"\nExecution Timeline ({len(timeline)} events):")
            for evt in timeline:
                lines.append(f"  - [{evt.event_type}] {evt.description}")

        return "\n".join(lines)

    @classmethod
    def explain_resource_protection(cls, resource_id: str, resource_type: str = "tab") -> str:
        """
        Explain why a resource was preserved or modified based on ownership policy.
        """
        tracker = ResourceOwnershipTracker.get_instance()
        owner = tracker.get_owner(resource_type, resource_id)

        if owner == ResourceOwner.USER:
            return (
                f"Resource '{resource_id}' belongs to ResourceOwner.USER. "
                f"According to Aura's Resource Protection Policy, user-created resources "
                f"are preserved and never closed automatically during cleanup."
            )
        elif owner == ResourceOwner.AURA:
            aura_res = [r for r in tracker.get_aura_resources() if r.resource_id == resource_id]
            reason = aura_res[0].reason if aura_res else "Aura task execution"
            return (
                f"Resource '{resource_id}' belongs to ResourceOwner.AURA (created for: '{reason}'). "
                f"It is managed and eligible for automatic cleanup."
            )
        return f"Resource '{resource_id}' owner is '{owner.value}'."
