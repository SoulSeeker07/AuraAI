"""
Memory Decay Engine
Location: src/memory/decay_engine.py

Calculates memory decay scores and identifies expired or low-importance memories
for pruning, while safeguarding permanent high-importance preferences.
"""

import datetime as dt

from .models import MemoryItem, MemoryType


class DecayEngine:
    """Evaluates memory decay and retention lifecycle."""

    def calculate_decay(self, memory: MemoryItem, now: dt.datetime | None = None) -> float:
        """
        Calculate current effective importance score (0.0 to 1.0) taking decay into account.

        Permanent items (PREFERENCE, high-importance items >= 0.9) do not decay.
        Short-term or working memories decay rapidly.
        """
        if now is None:
            now = dt.datetime.now()

        # Permanent safeguard
        if memory.type == MemoryType.PREFERENCE or memory.importance >= 0.9:
            return memory.importance

        try:
            last_ts = dt.datetime.fromisoformat(memory.last_accessed or memory.updated_at)
            days_old = (now - last_ts).total_seconds() / 86400.0
        except Exception:
            days_old = 0.0

        # Half-life by memory type (in days)
        half_life_days = {
            MemoryType.WORKING: 0.1,      # ~2.4 hours
            MemoryType.SHORT_TERM: 1.0,   # 1 day
            MemoryType.TASK: 3.0,         # 3 days
            MemoryType.EPISODIC: 30.0,    # 30 days
            MemoryType.PROCEDURAL: 60.0,  # 60 days
            MemoryType.SEMANTIC: 90.0,    # 90 days
            MemoryType.LONG_TERM: 180.0,  # 180 days
            MemoryType.PROJECT: 365.0,    # 1 year
        }.get(memory.type, 30.0)

        # Decay formula: importance * 0.5^(days / half_life)
        decay_factor = 0.5 ** (days_old / half_life_days)
        effective_importance = round(memory.importance * decay_factor, 4)
        return max(0.01, effective_importance)

    def is_expired(self, memory: MemoryItem, now: dt.datetime | None = None) -> bool:
        """Check if memory has passed explicit expiration date or decayed below threshold."""
        if now is None:
            now = dt.datetime.now()

        # Check explicit expiration date
        if memory.expires_at:
            try:
                exp_ts = dt.datetime.fromisoformat(memory.expires_at)
                if now >= exp_ts:
                    return True
            except Exception:
                pass

        # Permanent memories never expire automatically
        if memory.type == MemoryType.PREFERENCE or memory.importance >= 0.9:
            return False

        # Prune if effective decayed importance falls below 0.05
        effective = self.calculate_decay(memory, now)
        return effective < 0.05
