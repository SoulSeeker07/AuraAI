"""
Layer 10: Learning (Conservative)
=================================

Learning should be conservative. Never learn automatically.

Classification:
    Facts:       Immediate — "My favorite editor is VS Code." → Store.
    Preferences: Immediate — "Always answer in markdown." → Store.
    Behaviors:   Immediate — "When I ask 'Summarize today's session',
                              summarize RuntimeSession." → Store.
    Workflows:   Observed — Need repeated evidence.
                 Day 1: VS Code, GitHub, Teams
                 Day 2: VS Code, GitHub, Teams
                 Day 5: Same pattern.
                 Aura asks: "I've noticed this pattern. Create 'Work Mode'?"
                 Only then store.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LearnedItem:
    """A single item captured by the Learning Engine."""

    item_type: str  # 'fact', 'preference', 'behavior', 'workflow'
    trigger: str
    value: Any
    priority: str = "normal"
    source: str = "user"
    confirmed: bool = True  # Conservative: only confirmed items are stored
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_type": self.item_type,
            "trigger": self.trigger,
            "value": self.value,
            "priority": self.priority,
            "source": self.source,
            "confirmed": self.confirmed,
            "metadata": self.metadata,
        }


class LearningEngine:
    """
    Conservative Learning Engine.

    Only stores:
    * Explicit facts (user states a fact)
    * Explicit preferences (user states a preference)
    * Explicit behaviors (user teaches a behavior rule)
    * Confirmed workflows (user confirms a repeated pattern)

    Never learns automatically.
    """

    def __init__(self, behavior_store: Any | None = None):
        self.behavior_store = behavior_store
        self._learned_items: list[LearnedItem] = []
        self._workflow_observations: dict[str, int] = {}

    # ── Public API ──────────────────────────────────────────────────────────

    def learn_from_interaction(
        self,
        user_input: str,
        coordination_result: Any | None = None,
        verification: Any | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[LearnedItem]:
        """
        Learn from a completed interaction.

        Conservative: only explicit facts, preferences, and behaviors are stored.
        Workflows require repeated evidence and user confirmation.

        Args:
            user_input: The original user request.
            coordination_result: The execution result (optional).
            verification: The verification report (optional).
            context: Optional context.

        Returns:
            List of learned items (only confirmed items).
        """
        learned: list[LearnedItem] = []

        # 1. Explicit behavior corrections (user teaches Aura)
        behavior = self._extract_behavior(user_input)
        if behavior:
            learned.append(behavior)

        # 2. Explicit facts (user states a fact)
        fact = self._extract_fact(user_input)
        if fact:
            learned.append(fact)

        # 3. Explicit preferences (user states a preference)
        preference = self._extract_preference(user_input)
        if preference:
            learned.append(preference)

        # 4. Workflow patterns — observed, NOT stored automatically
        if coordination_result is not None:
            self._observe_workflow(user_input, coordination_result)

        # Persist only confirmed items
        for item in learned:
            if item.confirmed:
                self._persist(item, user_input)

        if learned:
            self._learned_items.extend(learned)
            logger.info(
                f"Learning Engine captured {len(learned)} confirmed items: "
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
            confirmed=True,
        )
        self._learned_items.append(item)
        self._persist(item, trigger)
        logger.info(f"Learning Engine: behavior rule learned for trigger '{trigger}'")
        return item

    def confirm_workflow(self, trigger: str) -> LearnedItem | None:
        """
        Confirm a workflow pattern after user approval.

        Called when the user says "yes" to:
        "I've noticed this pattern. Create 'Work Mode'?"
        """
        if trigger not in self._workflow_observations:
            return None

        item = LearnedItem(
            item_type="workflow",
            trigger=trigger,
            value={"pattern": trigger, "confirmed": True},
            priority="normal",
            source="user",
            confirmed=True,
        )
        self._learned_items.append(item)
        self._persist(item, trigger)
        logger.info(f"Learning Engine: workflow confirmed for '{trigger}'")
        return item

    def get_learned_items(self) -> list[LearnedItem]:
        """Get all learned items."""
        return self._learned_items.copy()

    def get_pending_workflow_suggestions(self) -> list[str]:
        """Get workflow patterns that have been observed multiple times."""
        return [
            trigger
            for trigger, count in self._workflow_observations.items()
            if count >= 3  # Need repeated evidence
        ]

    # ── Extraction Helpers (Conservative) ───────────────────────────────────

    def _extract_behavior(self, user_input: str) -> LearnedItem | None:
        """
        Detect explicit behavior rules.

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
                confirmed=True,
            )

        m = re.search(r"always\s+(.+?)\s+when\s+(.+)", text)
        if m:
            return LearnedItem(
                item_type="behavior",
                trigger=m.group(2).strip(),
                value={"action": m.group(1).strip()},
                priority="high",
                source="user",
                confirmed=True,
            )

        return None

    def _extract_fact(self, user_input: str) -> LearnedItem | None:
        """Detect explicit facts: 'remember that X'."""
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
                    confirmed=True,
                )
        return None

    def _extract_preference(self, user_input: str) -> LearnedItem | None:
        """Detect explicit preferences: 'I prefer X', 'always use X'."""
        text = user_input.lower()
        if "prefer" in text or "i'd rather" in text or "rather use" in text:
            return LearnedItem(
                item_type="preference",
                trigger=user_input,
                value=user_input,
                priority="normal",
                source="user",
                confirmed=True,
            )
        if "i like" in text or "i love" in text or "my favorite" in text:
            return LearnedItem(
                item_type="preference",
                trigger=user_input,
                value=user_input,
                priority="normal",
                source="user",
                confirmed=True,
            )
        return None

    def _observe_workflow(self, user_input: str, coordination_result: Any) -> None:
        """
        Observe workflow patterns — do NOT store automatically.

        Only counts repeated patterns. User confirmation is required
        before a workflow is stored.
        """
        # Only observe multi-step executions
        step_count = len(getattr(coordination_result, "step_results", []))
        if step_count < 2:
            return

        # Count this pattern
        key = user_input.lower().strip()
        self._workflow_observations[key] = self._workflow_observations.get(key, 0) + 1

        count = self._workflow_observations[key]
        if count == 3:
            logger.info(
                f"Learning Engine: workflow pattern observed 3 times for '{key}'. "
                f"Awaiting user confirmation."
            )

    # ── Persistence ─────────────────────────────────────────────────────────

    def _persist(self, item: LearnedItem, user_input: str) -> None:
        """Persist a confirmed item to the behavior store."""
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
                verified=item.confirmed,
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