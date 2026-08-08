"""
Adaptive Learning Engine
Location: src/core/learning/learning_engine.py
"""

import uuid

from .behavior_store import BehaviorStore
from .learning_types import LearningRule, RuleType
from .rule_matcher import RuleMatcher


class LearningEngine:
    """
    Core entry point for the Adaptive Learning subsystem.
    Analyses user inputs and executions to learn new custom behaviors.
    """

    def __init__(self, store: BehaviorStore | None = None):
        self.store = store or BehaviorStore()
        self.matcher = RuleMatcher(self.store)

    def analyze_feedback(self, user_goal: str, correction: str) -> LearningRule | None:
        """
        Explicitly learns a new behavior correction rule.
        """
        rule_id = f"rule_{uuid.uuid4().hex[:8]}"
        rule = LearningRule(
            rule_id=rule_id,
            rule_type=RuleType.BEHAVIOR,
            trigger=user_goal,
            behavior={"action": "correction", "details": correction},
        )
        self.store.add_rule(rule)
        return rule
