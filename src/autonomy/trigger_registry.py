"""
Trigger Registry (Persistent Storage & Lifecycle Management)
Location: src/autonomy/trigger_registry.py

Manages Trigger lifecycle transitions and persists trigger definitions to disk
(`storage/triggers.json`), allowing triggers to survive full process restarts.
"""

import json
import logging
from pathlib import Path
from typing import Any

from .models import ConcurrencyPolicy, EventProvenance, Trigger, TriggerState, TriggerType

logger = logging.getLogger(__name__)


class TriggerRegistry:
    """
    Registry for proactive triggers with JSON file persistence.
    """

    def __init__(self, storage_path: str | Path | None = None):
        if storage_path is None:
            storage_path = Path("storage/triggers.json")
        self.storage_path = Path(storage_path)
        self._triggers: dict[str, Trigger] = {}
        self._dedup_keys: set[str] = set()

        self.load_triggers()

    def register_trigger(self, trigger: Trigger) -> bool:
        """
        Register a new trigger. Rejects if dedup_key already exists.
        """
        if trigger.dedup_key and trigger.dedup_key in self._dedup_keys:
            logger.warning(f"[TriggerRegistry] Trigger with dedup_key '{trigger.dedup_key}' already registered — skipping duplicate.")
            return False

        trigger.state = TriggerState.ARMED if trigger.enabled else TriggerState.REGISTERED
        self._triggers[trigger.trigger_id] = trigger
        if trigger.dedup_key:
            self._dedup_keys.add(trigger.dedup_key)

        self.save_triggers()
        logger.info(f"[TriggerRegistry] Registered trigger '{trigger.trigger_id}' ({trigger.trigger_type.value}) -> state={trigger.state.value}")
        return True

    def get_trigger(self, trigger_id: str) -> Trigger | None:
        return self._triggers.get(trigger_id)

    def list_triggers(self, enabled_only: bool = False) -> list[Trigger]:
        if enabled_only:
            return [t for t in self._triggers.values() if t.enabled]
        return list(self._triggers.values())

    def update_state(self, trigger_id: str, new_state: TriggerState, provenance: EventProvenance | None = None) -> bool:
        trigger = self._triggers.get(trigger_id)
        if not trigger:
            return False

        trigger.state = new_state
        if provenance:
            trigger.last_provenance = provenance
            trigger.last_fired_at = provenance.fired_at

        self.save_triggers()
        logger.debug(f"[TriggerRegistry] Trigger '{trigger_id}' state updated to '{new_state.value}'")
        return True

    def set_enabled(self, trigger_id: str, enabled: bool) -> bool:
        trigger = self._triggers.get(trigger_id)
        if not trigger:
            return False

        trigger.enabled = enabled
        trigger.state = TriggerState.ARMED if enabled else TriggerState.REGISTERED
        self.save_triggers()
        logger.info(f"[TriggerRegistry] Trigger '{trigger_id}' enabled set to {enabled}")
        return True

    def remove_trigger(self, trigger_id: str) -> bool:
        trigger = self._triggers.pop(trigger_id, None)
        if trigger:
            if trigger.dedup_key:
                self._dedup_keys.discard(trigger.dedup_key)
            self.save_triggers()
            logger.info(f"[TriggerRegistry] Removed trigger '{trigger_id}'")
            return True
        return False

    def save_triggers(self) -> None:
        """Persist registered triggers to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {t_id: t.to_dict() for t_id, t in self._triggers.items()}
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"[TriggerRegistry] Persisted {len(self._triggers)} triggers to '{self.storage_path}'")
        except Exception as e:
            logger.error(f"[TriggerRegistry] Failed to save triggers to disk: {e}")

    def load_triggers(self) -> None:
        """Load triggers from disk."""
        if not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._triggers.clear()
            self._dedup_keys.clear()

            for t_id, t_dict in data.items():
                t = Trigger.from_dict(t_dict)
                # On process restart, set ARMED if enabled
                if t.enabled and t.state == TriggerState.RUNNING:
                    t.state = TriggerState.ARMED
                self._triggers[t_id] = t
                if t.dedup_key:
                    self._dedup_keys.add(t.dedup_key)

            logger.info(f"[TriggerRegistry] Loaded {len(self._triggers)} triggers from '{self.storage_path}'")
        except Exception as e:
            logger.error(f"[TriggerRegistry] Failed to load triggers from disk: {e}")
