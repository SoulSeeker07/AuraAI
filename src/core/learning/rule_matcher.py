"""
Rule Matcher for Adaptive Learning Runtime
Location: src/core/learning/rule_matcher.py
"""

from typing import Optional
from .learning_types import LearningRule
from .behavior_store import BehaviorStore

class RuleMatcher:
    """
    Matches user requests and session goals to learned behavioral rules.
    """

    def __init__(self, store: BehaviorStore):
        self.store = store

    def match(self, goal: str) -> Optional[LearningRule]:
        goal_lower = goal.lower().strip()
        for rule in self.store.list_rules():
            if rule.trigger.lower() == goal_lower or rule.trigger.lower() in goal_lower:
                return rule
        return None
