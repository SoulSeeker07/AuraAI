"""
Layer 5: Learning Engine
========================

Learning occurs only after the task is complete.

The Learning Engine captures:
    * new facts
    * user preferences
    * behavior corrections
    * workflow patterns

Example:
    User: 'When I ask "Summarize today's session",
           summarize everything we worked on.'

    Learning stores:
        Type: BehaviorRule
        Trigger: Summarize today's session
        Action: Summarize RuntimeSession
        Priority: High

Next time, the DMM consults learned behavior before planning.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from .executor import PlanResult
from .reflection import ReflectionOutcome

logger = logging.getLogger(__name__)


@dataclass
class LearnedItem:
    """A single item captured by the Learning Engine."""

    item_type: str  # 'fact', 'preference', 'behavior', 'workflow'
    trigger: str
    value: Any
    priority: str = "normal"
    source: str = "interaction"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_type": self.item_type,
            "trigger": self.trigger,
            "value": self.value,
            "priority": self.priority,
            "source": self.source,
            "metadata": self.metadata,
        }


class LearningEngine:
    """
    Captures new facts, preferences, behavior corrections, and workflow
    patterns after task completion.

    The DMM consults learned behavior before planning.
    """

    def __init__(self, behavior_store: Any | None = None):
        self.behavior_store = behavior_store
        self._learned_items: list[LearnedItem] = []

    def learn_from_interaction(
        self,
        user_input: str,
        plan_result: PlanResult,
        reflection: ReflectionOutcome,
        context: dict[str, Any] | None = None,
    ) -> list[LearnedItem]:
        """Learn from a completed interaction (execution + reflection)."""
        learned: list[LearnedItem] = []

        correction = self._extract_behavior_correction(user_input)
        if correction:
            learned.append(correction)

        workflow = self._extract_workflow_pattern(plan_result, user_input)
        if workflow:
            learned.append(workflow)

        fact = self._extract_fact(user_input)
        if fact:
            learned.append(fact)

        preference = self._extract_preference(user_input)
        if preference:
            learned.append(preference)

        for item in learned:
            self._persist(item, user_input)

        if learned:
            self._learned_items.extend(learned)
            logger.info(
                f"Learning Engine captured {len(learned)} items: "
                f"{[i.item_type for i in learned]}"
            )

        return learned

    def learn_behavior_rule(
        self, trigger: str, action: str, priority: str = "high"
    ) -> LearnedItem:
        """Explicitly learn a behavior rule from user instruction."""
        item = LearnedItem(
            item_type="behavior",
            trigger=trigger,
            value={"action": action},
            priority=priority,
            source="user",
        )
        self._learned_items.append(item)
        self._persist(item, trigger)
        logger.info(f"Learning Engine: behavior rule learned for trigger '{trigger}'")
        return item

    def get_learned_items(self) -> list[LearnedItem]:
        """Get all learned items."""
        return self._learned_items.copy()

    def _extract_behavior_correction(self, user_input: str) -> LearnedItem | None:
        """
        Detect behavior corrections.

        Patterns:
            "when I ask X, do Y"
            "always do X when Y"
        """
        text = user_input.lower()
        import re

        m = re.search(
            r"when i (?:ask|say)[\"']?(.+?)[\"']?[,:]?\s*"
            r"(?:do|summarize|open|run|use|give)\s+(.+)",
            text,
        )
        if m:
            return LearnedItem(
                item_type="behavior",
                trigger=m.group(1).strip(),
                value={"action": m.group(2).strip()},
                priority="high",
                source="user",
            )

        m = re.search(r"always\s+(.+?)\s+when\s+(.+)", text)
        if m:
            return LearnedItem(
                item_type="behavior",
                trigger=m.group(2).strip(),
                value={"action": m.group(1).strip()},
                priority="high",
                source="user",
            )

        return None

    def _extract_workflow_pattern(
        self, plan_result: PlanResult, user_input: str
    ) -> LearnedItem | None:
        """Capture repeated multi-step workflows as replayable patterns."""
        if plan_result.success and len(plan_result.step_results) >= 2:
            return LearnedItem(
                item_type="workflow",
                trigger=user_input,
                value={
                    "steps": len(plan_result.step_results),
                    "plan_id": plan_result.plan_id,
                    "replayable": True,
                },
                priority="normal",
                source="execution",
            )
        return None

    def _extract_fact(self, user_input: str) -> LearnedItem | None:
        """Detect facts: 'remember that X', 'I like X'."""
        text = user_input.lower()
        if text.startswith("remember that") or text.startswith("remember"):
            fact_value = (
                user_input.replace("remember that", "").replace("remember", "").strip()
            )
            if fact_value:
                return LearnedItem(
                    item_type="fact",
                    trigger=user_input,
                    value=fact_value,
                    priority="normal",
                    source="user",
                )
        if "i like" in text or "i love" in text or "my favorite" in text:
            return LearnedItem(
                item_type="preference",
                trigger=user_input,
                value=user_input,
                priority="normal",
                source="user",
            )
        return None

    def _extract_preference(self, user_input: str) -> LearnedItem | None:
        """Detect preference statements."""
        text = user_input.lower()
        if "prefer" in text or "i'd rather" in text or "rather use" in text:
            return LearnedItem(
                item_type="preference",
                trigger=user_input,
                value=user_input,
                priority="normal",
                source="user",
            )
        return None

    def _persist(self, item: LearnedItem, user_input: str) -> None:
        """Persist to behavior store for DMM consultation."""
        if self.behavior_store is None:
            return
        try:
            from src.core.learning.learning_types import LearningRule, RuleType

            rule_type_map = {
                "fact": RuleType.FACT,
                "preference": RuleType.PREFERENCE,
                "behavior": RuleType.BEHAVIOR,
                "workflow": RuleType.WORKFLOW,
            }
            rule = LearningRule(
                rule_id=f"rule_{uuid.uuid4().hex[:8]}",
                rule_type=rule_type_map.get(item.item_type, RuleType.BEHAVIOR),
                trigger=item.trigger,
                behavior=item.value,
                scope="global",
                confidence=1.0 if item.priority == "high" else 0.8,
                created_by=item.source,
                verified=True,
                metadata={"priority": item.priority, "original_input": user_input},
            )
            self.behavior_store.add_rule(rule)
            logger.info(
                f"Learning Engine persisted {item.item_type} rule "
                f"'{rule.rule_id}' to behavior store"
            )
        except Exception as e:
            logger.debug(f"Behavior store persistence skipped: {e}")

    def register_behavior_store(self, store: Any) -> None:
        """Register a behavior store for persistence."""
        self.behavior_store = store


__all__ = ["LearningEngine", "LearnedItem"]