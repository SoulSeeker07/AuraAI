"""
Aura Cognitive Architecture (ACA) — Schemas
===========================================

Shared data contracts for the cognitive architecture.
"""

from .cognitive_state import CognitiveState, Blackboard
from .thought import Thought, DecisionContext, Goal, Entity, Confidence, SafetyAssessment
from .execution_map import ExecutionMap, ExecutionStep, FallbackOption, VerificationCriterion
from .task_graph import TaskGraph, TaskNode
from .runtime_session import RuntimeSession
from .artifact import Artifact

__all__ = [
    "CognitiveState",
    "Blackboard",
    "Thought",
    "DecisionContext",
    "Goal",
    "Entity",
    "Confidence",
    "SafetyAssessment",
    "ExecutionMap",
    "ExecutionStep",
    "FallbackOption",
    "VerificationCriterion",
    "TaskGraph",
    "TaskNode",
    "RuntimeSession",
    "Artifact",
]