"""
Behavior Store for Adaptive Learning Runtime
Location: src/core/learning/behavior_store.py
"""

import json
from pathlib import Path

from .learning_types import LearningRule, RuleType


class BehaviorStore:
    """
    Local persistent storage manager for custom learned behaviors and preference rules.
    """

    def __init__(self, store_path: Path | None = None):
        if store_path is None:
            from pathlib import Path

            root = Path(__file__).resolve().parent.parent.parent.parent
            store_path = root / "Data" / "BehaviorStore.json"
        self.store_path = store_path
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_rules()

    def _load_rules(self) -> None:
        try:
            if self.store_path.exists():
                data = json.loads(self.store_path.read_text(encoding="utf-8"))
                self._rules = {
                    r_id: LearningRule(
                        rule_id=r_id,
                        rule_type=RuleType(r["rule_type"]),
                        trigger=r["trigger"],
                        behavior=r["behavior"],
                        scope=r.get("scope", "global"),
                        confidence=r.get("confidence", 1.0),
                        created_by=r.get("created_by", "user"),
                        verified=r.get("verified", True),
                        created_at=r.get("created_at"),
                        metadata=r.get("metadata", {}),
                    )
                    for r_id, r in data.items()
                }
            else:
                self._rules = {}
        except Exception:
            self._rules = {}

    def _save_rules(self) -> None:
        try:
            data = {r_id: r.to_dict() for r_id, r in self._rules.items()}
            self.store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def add_rule(self, rule: LearningRule) -> None:
        self._rules[rule.rule_id] = rule
        self._save_rules()

    def get_rule(self, rule_id: str) -> LearningRule | None:
        return self._rules.get(rule_id)

    def list_rules(self) -> list[LearningRule]:
        return list(self._rules.values())

    def clear(self) -> None:
        self._rules.clear()
        self._save_rules()
