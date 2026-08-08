"""
Rule Matcher for Adaptive Learning Runtime
Location: src/core/learning/rule_matcher.py
"""

from .behavior_store import BehaviorStore
from .learning_types import LearningRule


class RuleMatcher:
    """
    Matches user requests and session goals to learned behavioral rules.
    """

    def __init__(self, store: BehaviorStore):
        self.store = store

    def match(self, goal: str) -> LearningRule | None:
        goal_lower = goal.lower().strip()
        for rule in self.store.list_rules():
            if rule.trigger.lower() == goal_lower or rule.trigger.lower() in goal_lower:
                return rule
        return None
