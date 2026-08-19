"""
Autonomy Engine & Event Runtime Module (M24)
Location: src/autonomy/__init__.py

Exposes AuraEvent contract, EventRuntime core engine, EventTraceRecord,
EventAssessment, EventInterpreter, PolicyDecision, PolicyDecisionType, AutonomyPolicyGate,
FilesystemWatcher, ProcessMonitor, CorrelatedEventGroup, EventSource, EventType, EventUrgency.
"""

from .events import (
    AuraEvent,
    EventSource,
    EventType,
    EventUrgency,
    EventValidationError,
)
from .event_runtime import (
    CorrelatedEventGroup,
    EventRuntime,
    EventTraceRecord,
    compute_semantic_fingerprint,
    normalize_resource_key,
)
from .interpreter import (
    EventAssessment,
    EventInterpreter,
    IContextResolver,
    DefaultContextResolver,
)
from .models import ConcurrencyPolicy, EventProvenance, Trigger, TriggerState, TriggerType
from .policy_gate import (
    AutonomyPolicyGate,
    PolicyDecision,
    PolicyDecisionType,
)
from .trigger_registry import TriggerRegistry
from .watchers import FilesystemWatcher, ProcessMonitor

__all__ = [
    "AuraEvent",
    "EventSource",
    "EventType",
    "EventUrgency",
    "EventValidationError",
    "EventRuntime",
    "EventTraceRecord",
    "CorrelatedEventGroup",
    "EventAssessment",
    "EventInterpreter",
    "IContextResolver",
    "DefaultContextResolver",
    "PolicyDecision",
    "PolicyDecisionType",
    "AutonomyPolicyGate",
    "FilesystemWatcher",
    "ProcessMonitor",
    "compute_semantic_fingerprint",
    "normalize_resource_key",
    "TriggerRegistry",
    "Trigger",
    "TriggerState",
    "TriggerType",
    "ConcurrencyPolicy",
    "EventProvenance",
]
