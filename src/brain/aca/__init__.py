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

from .fusion_engine import FusionEngine
from .confidence_gate import ConfidenceGate
from .strategy_engine import StrategyEngine, ACAPlanner
from .goal_manager import GoalManager, Goal
from .policy_engine import PolicyEngine, PolicyDecision
from .artifact_manager import ArtifactManager
from .aca_brain import ACABrain, ACAResponse

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