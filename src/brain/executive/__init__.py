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

from .execution_map import (
    Capability,
    ExecutionMap,
    ExecutionStep,
    FallbackOption,
    SuccessCriteria,
)
from .dmm import DecisionMakingModule, ClarificationRequest
from .planner import ExecutivePlanner
from .executor import ExecutiveExecutor
from .reflection import ReflectionEngine
from .learning import LearningEngine
from .executive_brain import ExecutiveBrain

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