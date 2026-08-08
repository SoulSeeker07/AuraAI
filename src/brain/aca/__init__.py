"""
Aura Cognitive Architecture (ACA)
=================================

A staged cognitive architecture composed of perception, reasoning,
planning, execution, reflection, and learning.

    USER
      │
      ▼
Stage 0: Context & World Understanding
      │
      ▼
Stage 1: DMM (Decision Making Module)
      │
      ▼
Stage 2: Planning & Strategy
      │
      ▼
Stage 3: Execution Coordination
      │
      ▼
Stage 4: Reflection & Learning
"""

from .aca_brain import ACABrain, ACAResponse
from .artifact_manager import ArtifactManager
from .confidence_gate import ConfidenceGate
from .fusion_engine import FusionEngine
from .goal_manager import Goal, GoalManager
from .policy_engine import PolicyDecision, PolicyEngine
from .strategy_engine import ACAPlanner, StrategyEngine

__all__ = [
    "FusionEngine",
    "ConfidenceGate",
    "StrategyEngine",
    "ACAPlanner",
    "GoalManager",
    "Goal",
    "PolicyEngine",
    "PolicyDecision",
    "ArtifactManager",
    "ACABrain",
    "ACAResponse",
]
