"""
EventInterpreter & EventAssessment Engine (M24 Phase 3)
Location: src/autonomy/interpreter.py

Transforms raw AuraEvent and CorrelatedEventGroup signals into structured, immutable
EventAssessment records using situational context from WorldModel and Memory.

Architectural Invariants:
1. Interpretation != Execution: Evaluates meaning and candidate intent only; NEVER calls capabilities or tools.
2. Immutability: EventAssessment is frozen and forms the 3rd link in the causal audit chain:
   event_id -> correlation_id -> assessment_id -> policy_decision_id -> plan_id -> execution_id -> observation_id
3. Noise Suppression: Suppresses low-relevance or low-confidence telemetry before reaching AutonomyPolicyGate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Protocol
import uuid

from .events import AuraEvent, EventSource, EventType, EventUrgency, _freeze_payload, _unfreeze_payload
from .event_runtime import CorrelatedEventGroup

logger = logging.getLogger(__name__)


# Ignored noise file patterns for filesystem events
NOISE_FILE_PATTERNS = {
    ".git", ".git/", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".mypy_cache", ".tmp", ".swp", ".lock", "thumbs.db", "desktop.ini"
}

# Recognized engineering build/test executables
ENGINEERING_PROCESSES = {
    "pytest", "pytest.exe", "python", "python.exe", "cargo", "cargo.exe",
    "npm", "npm.cmd", "node", "node.exe", "ruff", "ruff.exe", "tsc", "tsc.cmd"
}


@dataclass(frozen=True)
class EventAssessment:
    """
    Immutable assessment of an event's semantic meaning, relevance, and candidate intent.

    Attributes:
        assessment_id: Unique assessment identifier (format: asm_<uuid4_hex>)
        event_id: Causal root event identifier matching AuraEvent.event_id
        correlation_id: Causal correlation identifier matching AuraEvent.correlation_id
        relevance: Evaluated relevance score [0.0, 1.0]
        confidence: Evaluated confidence score [0.0, 1.0]
        is_actionable: True if both relevance and confidence meet thresholds and candidate_intent exists
        candidate_intent: Structured proposed goal statement (None if suppressed or not actionable)
        candidate_intent_type: Structured intent category (e.g. 'engineering.diagnose', 'workspace.evaluate')
        reason: Human-readable explanation for assessment scores and classification
        context_resolution: Immutable mapping of situational facts resolved from WorldModel / Memory
        created_at: UTC ISO 8601 timestamp string
        metadata: Immutable auxiliary metadata
    """
    assessment_id: str
    event_id: str
    correlation_id: str
    relevance: float
    confidence: float
    is_actionable: bool
    candidate_intent: str | None
    candidate_intent_type: str | None
    reason: str
    context_resolution: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: MappingProxyType[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "event_id": self.event_id,
            "correlation_id": self.correlation_id,
            "relevance": self.relevance,
            "confidence": self.confidence,
            "is_actionable": self.is_actionable,
            "candidate_intent": self.candidate_intent,
            "candidate_intent_type": self.candidate_intent_type,
            "reason": self.reason,
            "context_resolution": _unfreeze_payload(self.context_resolution),
            "created_at": self.created_at,
            "metadata": _unfreeze_payload(self.metadata),
        }

    def to_json(self, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventAssessment":
        return cls(
            assessment_id=data["assessment_id"],
            event_id=data["event_id"],
            correlation_id=data["correlation_id"],
            relevance=float(data["relevance"]),
            confidence=float(data["confidence"]),
            is_actionable=bool(data["is_actionable"]),
            candidate_intent=data.get("candidate_intent"),
            candidate_intent_type=data.get("candidate_intent_type"),
            reason=data.get("reason", ""),
            context_resolution=_freeze_payload(data.get("context_resolution", {})),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            metadata=_freeze_payload(data.get("metadata", {})),
        )


class IContextResolver(Protocol):
    """Protocol for querying situational computing context (e.g. WorldModel)."""
    async def get_active_context(self, entity_hint: str) -> dict[str, Any]:
        ...


class DefaultContextResolver:
    """Default fallback context resolver that queries WorldModel when available."""

    def __init__(self, world_model: Any | None = None) -> None:
        self.world_model = world_model

    async def get_active_context(self, entity_hint: str) -> dict[str, Any]:
        if self.world_model is not None:
            try:
                res = await self.world_model.query(entity_hint)
                return {"summary": res.summary, "fact_count": len(res.facts)}
            except Exception as e:
                logger.debug(f"[DefaultContextResolver] WorldModel query failed: {e}")
        return {"active_workspace": os.getcwd()}


class EventInterpreter:
    """
    Situational Event Interpreter.
    Evaluates raw telemetry to determine relevance, confidence, and candidate intents.
    """

    def __init__(
        self,
        relevance_threshold: float = 0.5,
        confidence_threshold: float = 0.6,
        context_resolver: IContextResolver | None = None,
    ) -> None:
        self.relevance_threshold = relevance_threshold
        self.confidence_threshold = confidence_threshold
        self.context_resolver = context_resolver or DefaultContextResolver()

    async def interpret(
        self,
        event: AuraEvent,
        group: CorrelatedEventGroup | None = None,
    ) -> EventAssessment:
        """
        Main interpretation pipeline:
        1. Evaluates signal semantics.
        2. Resolves contextual world state.
        3. Correlates multi-signal evidence.
        4. Calculates relevance and confidence.
        5. Produces immutable EventAssessment.
        """
        assessment_id = f"asm_{uuid.uuid4().hex}"
        corr_id = event.correlation_id

        # 1. Resolve active environmental context
        resource_hint = str(event.payload.get("path") or event.payload.get("process_name") or "workspace")
        context_facts = await self.context_resolver.get_active_context(resource_hint)
        if group is not None:
            context_facts["correlated_event_count"] = len(group.events)
            context_facts["correlated_group_id"] = group.correlation_id

        # 2. Heuristic Semantic Evaluation
        relevance, confidence, candidate_intent, intent_type, reason = self._evaluate_semantics(
            event, group, context_facts
        )

        # 3. Apply Actionability Gate (Threshold Filtering)
        is_actionable = (
            relevance >= self.relevance_threshold
            and confidence >= self.confidence_threshold
            and candidate_intent is not None
        )

        if not is_actionable and candidate_intent is not None:
            reason = f"Suppressed: score below actionability threshold (rel={relevance:.2f}, conf={confidence:.2f}). {reason}"
            candidate_intent = None
            intent_type = None

        return EventAssessment(
            assessment_id=assessment_id,
            event_id=event.event_id,
            correlation_id=corr_id,
            relevance=relevance,
            confidence=confidence,
            is_actionable=is_actionable,
            candidate_intent=candidate_intent,
            candidate_intent_type=intent_type,
            reason=reason,
            context_resolution=_freeze_payload(context_facts),
            metadata=_freeze_payload({"source": event.source.value, "event_type": event.event_type}),
        )

    def _evaluate_semantics(
        self,
        event: AuraEvent,
        group: CorrelatedEventGroup | None,
        context_facts: dict[str, Any],
    ) -> tuple[float, float, str | None, str | None, str]:
        """
        Determines relevance, confidence, and candidate intent for an event.
        """
        source = event.source
        event_type = event.event_type
        payload = event.payload

        # Case A: Filesystem Events
        if source == EventSource.FILESYSTEM:
            path_str = str(payload.get("path") or payload.get("file") or "").lower()
            
            # Check for noise paths
            if any(noise in path_str for noise in NOISE_FILE_PATTERNS):
                return 0.1, 0.9, None, None, f"Suppressed: path '{path_str}' matches noise file filter."

            if not path_str:
                return 0.2, 0.5, None, None, "Suppressed: filesystem event missing path payload."

            # Significant project source/config file
            ext = Path(path_str).suffix
            if ext in [".py", ".ts", ".js", ".json", ".toml", ".yaml", ".yml", ".rs", ".go"]:
                # If part of a correlation group with multiple files
                if group and len(group.events) > 1:
                    return (
                        0.75,
                        0.85,
                        f"Evaluate multi-file changes in workspace ({len(group.events)} events)",
                        "workspace.evaluate",
                        f"Significant source modification detected across {len(group.events)} correlated events.",
                    )
                return (
                    0.70,
                    0.80,
                    f"Inspect modified source file '{Path(path_str).name}'",
                    "workspace.inspect",
                    f"Source file '{path_str}' modified in workspace.",
                )

            return 0.35, 0.60, None, None, f"Low relevance: non-code file extension '{ext}'."

        # Case B: Process Events
        elif source == EventSource.PROCESS:
            proc_name = str(payload.get("process_name") or payload.get("process") or "").lower().strip()
            exit_code = payload.get("exit_code")

            if event_type in [EventType.PROCESS_EXITED.value, EventType.PROCESS_CRASHED.value]:
                if exit_code is not None and exit_code != 0:
                    # Non-zero exit code on build/test process
                    if any(eng in proc_name for eng in ENGINEERING_PROCESSES):
                        return (
                            0.95,
                            0.90,
                            f"Diagnose failure in build/test process '{proc_name}' (exit code {exit_code})",
                            "engineering.diagnose",
                            f"Process '{proc_name}' exited with error status {exit_code}.",
                        )
                    # Generic process failure
                    return (
                        0.80,
                        0.75,
                        f"Investigate abnormal exit of process '{proc_name}' (exit code {exit_code})",
                        "system.diagnose",
                        f"Process '{proc_name}' exited with non-zero exit code {exit_code}.",
                    )
                else:
                    # Clean exit code 0
                    return 0.25, 0.90, None, None, f"Routine: process '{proc_name}' exited cleanly (code 0)."

            elif event_type == EventType.PROCESS_STARTED.value:
                return 0.30, 0.80, None, None, f"Informational: process '{proc_name}' started."

        # Case C: System & Power Events
        elif source == EventSource.SYSTEM:
            if event_type in [EventType.SYSTEM_BATTERY_LOW.value, EventType.SYSTEM_POWER_CHANGED.value]:
                return (
                    0.90,
                    0.95,
                    "Handle system power threshold change and optimize autonomous workloads",
                    "system.power_management",
                    "Critical hardware power threshold state change detected.",
                )
            return 0.40, 0.70, None, None, f"System event '{event_type}' noted."

        # Case D: Network Events
        elif source == EventSource.NETWORK:
            if event_type == EventType.NETWORK_DISCONNECTED.value:
                return (
                    0.85,
                    0.90,
                    "Adapt autonomous network jobs to offline mode",
                    "network.offline_adapt",
                    "Network disconnection event detected.",
                )
            return 0.30, 0.80, None, None, f"Routine network event '{event_type}'."

        # Fallback / Custom
        if event.urgency in [EventUrgency.HIGH, EventUrgency.CRITICAL]:
            return (
                0.75,
                0.70,
                f"Assess high urgency event '{event.event_type}'",
                "system.alert",
                f"Urgent event received from source '{event.source.value}'.",
            )

        return 0.20, 0.50, None, None, f"Unclassified event '{event.event_type}' with low default relevance."
