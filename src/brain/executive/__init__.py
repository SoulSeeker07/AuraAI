"""
Aura Executive Brain — The Cognitive Center of Aura
====================================================

The Executive Brain is the only component that "thinks."
Everything else simply executes.

Architecture:
    AuraCore
        ↓
    ExecutiveBrain
        ├── Layer 1 : DMM (Decision Making Module)
        ├── Layer 2 : Planner
        ├── Layer 3 : Executor
        ├── Layer 4 : Reflection
        └── Layer 5 : Learning
        ↓
    MasterOrchestrator
        ↓
    Execution Engines

The Golden Rule:
    The Executive Brain thinks. The Planner organizes.
    The Engines execute. Reflection validates. Learning improves.
"""

from .dmm import ClarificationRequest, DecisionMakingModule
from .execution_map import (
    Capability,
    ExecutionMap,
    ExecutionStep,
    FallbackOption,
    SuccessCriteria,
)
from .executive_brain import ExecutiveBrain
from .executor import ExecutiveExecutor
from .learning import LearningEngine
from .planner import ExecutivePlanner
from .reflection import ReflectionEngine

__all__ = [
    "Capability",
    "ExecutionMap",
    "ExecutionStep",
    "FallbackOption",
    "SuccessCriteria",
    "DecisionMakingModule",
    "ClarificationRequest",
    "ExecutivePlanner",
    "ExecutiveExecutor",
    "ReflectionEngine",
    "LearningEngine",
    "ExecutiveBrain",
]
