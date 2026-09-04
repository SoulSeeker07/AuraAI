"""
Suspend / Resume Governance Test Invariant Harness
Location: tests/helpers/suspend_resume_invariants.py

Provides reusable test fixtures and assertions enforcing the three non-negotiable
architectural invariants across all pause/suspend/resume subsystems in AuraAI:
  1. Narrow Single-Use Scoping: Tickets bind strictly to (ticket_id, subtask_id).
  2. Active Downstream Re-gating: Resumed or drained queues re-evaluate ExecutionPolicy.
  3. Dispatch-Level Idempotency: Pruned nodes are never dispatched to any backend.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DispatchEvent:
    """Recorded capability dispatch event at the universal orchestrator dispatch point."""
    task_id: str
    capability: str
    backend_name: str
    parameters: dict[str, Any] = field(default_factory=dict)


class UniversalDispatchSpy:
    """
    Universal test spy tracking all capability dispatches across any backend.
    Enforces Invariant 3 (Dispatch-Level Idempotency).
    """

    def __init__(self) -> None:
        self.events: list[DispatchEvent] = []

    def record(
        self,
        task_id: str,
        capability: str,
        backend_name: str,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            DispatchEvent(
                task_id=task_id,
                capability=capability,
                backend_name=backend_name,
                parameters=parameters or {},
            )
        )

    @property
    def capabilities(self) -> list[str]:
        return [e.capability for e in self.events]

    @property
    def task_ids(self) -> list[str]:
        return [e.task_id for e in self.events]

    def invocation_count(self, key: str) -> int:
        """Count invocations matching capability name or task_id."""
        return sum(1 for e in self.events if e.capability == key or e.task_id == key)

    def assert_idempotent_sequence(self, expected_capabilities: list[str]) -> None:
        """
        Enforce Invariant 3:
        Asserts that every expected capability was dispatched exactly once,
        in the strict expected topological order, with zero double-executions.
        """
        actual = self.capabilities
        assert actual == expected_capabilities, (
            f"Execution sequence mismatch or double-run detected!\n"
            f"Expected strictly once in order: {expected_capabilities}\n"
            f"Actual dispatch sequence:       {actual}"
        )
        counts = Counter(actual)
        for cap in expected_capabilities:
            assert counts[cap] == 1, (
                f"Capability '{cap}' was dispatched {counts[cap]} times; expected strictly 1."
            )

    def assert_dispatched_once(self, key: str) -> None:
        """Assert that a capability or task_id was dispatched exactly once."""
        count = self.invocation_count(key)
        assert count == 1, f"Expected '{key}' to be dispatched exactly once, got {count}."

    def assert_never_dispatched(self, key: str) -> None:
        """Assert that a capability or task_id was never dispatched to any backend."""
        count = self.invocation_count(key)
        assert count == 0, f"Expected '{key}' to never be dispatched, but got {count} invocations."


def assert_narrow_ticket_scoping(
    ticket_1: str,
    ticket_2: str,
    subtask_1: str,
    subtask_2: str,
) -> None:
    """
    Enforce Invariant 1 (Narrow Single-Use Scoping):
    Asserts that subsequent sensitive nodes generate distinct approval tickets
    bound to different subtasks, preventing session-wide blanket bypass.
    """
    assert ticket_1, "Initial gated node must generate a valid ticket"
    assert ticket_2, "Downstream gated node must generate a valid ticket"
    assert ticket_1 != ticket_2, (
        f"Ticket scope bleed: subsequent gated node reused ticket '{ticket_1}' "
        f"instead of generating an independent approval ticket."
    )
    assert subtask_1 != subtask_2, "Subtask IDs for distinct nodes must differ"


def assert_downstream_suspended(
    result: Any,
    expected_subtask_id: str,
) -> str:
    """
    Enforce Invariant 2 (Active Downstream Re-gating):
    Asserts that execution paused before the expected sensitive subtask
    and returned a suspended session payload rather than completing silently.
    Returns the newly generated suspended_ticket_id.
    """
    assert result.success is False, (
        f"Downstream re-gating bypassed: execution succeeded when it should have suspended on '{expected_subtask_id}'"
    )
    assert result.data.get("is_suspended") is True, (
        f"Expected session to be suspended before '{expected_subtask_id}', but data['is_suspended'] was {result.data.get('is_suspended')}"
    )
    ticket_id = result.data.get("suspended_ticket_id")
    assert ticket_id, f"Missing suspended_ticket_id in suspended result for '{expected_subtask_id}'"
    return str(ticket_id)
