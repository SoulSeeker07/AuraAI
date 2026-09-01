"""
VisualWorkingMemory — In-Memory Referential Ring Buffer for Cross-App Dictation
Location: src/core/visual_memory.py

Maintains short-lived grounded visual targets per FocusManager task thread.
Resolves deictic phrases ("that file", "it", "this one") and 1-turn verbal
alternative corrections ("no, the other one", "the second one").

Key Invariants:
  1. Thread-Isolated: Slices are keyed by FocusManager.get_current().task_id.
  2. Short-Lived: Ring buffer capped at 5 items, TTL of 3 turns.
  3. App-Switch Decay: Targets decay immediately when foreground application changes.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

from vision.grounding_engine import GroundedTarget

logger = logging.getLogger(__name__)

MAX_TARGETS_PER_THREAD = 5
DEFAULT_TTL_TURNS = 3


@dataclass
class VisualMemoryEntry:
    """A memory entry holding grounded targets from a single interaction turn."""

    targets: list[GroundedTarget]
    app_name: str
    turn_index: int
    timestamp: float = field(default_factory=time.time)


class VisualWorkingMemory:
    """
    Thread-safe in-memory ring buffer tracking recent visual targets for
    cross-app deictic pronoun and referential phrase resolution.
    """

    _instance: Optional["VisualWorkingMemory"] = None
    _lock: threading.Lock = threading.Lock()

    # Regex patterns for standard referential phrases
    REFERENTIAL_PATTERNS = [
        re.compile(r"\b(?:that|this|the)\s+(?:file|folder|button|link|item|input|field|tab|window)\b", re.IGNORECASE),
        re.compile(r"\b(?:that\s+one|this\s+one|the\s+other\s+one)\b", re.IGNORECASE),
        re.compile(r"\b(?:it|that|this)\b", re.IGNORECASE),
    ]

    # Regex patterns for immediate 1-turn verbal alternative corrections
    ALTERNATIVE_PATTERNS = [
        re.compile(r"\b(?:no,?\s+)?(?:the\s+)?other\s+one\b", re.IGNORECASE),
        re.compile(r"\b(?:no,?\s+)?(?:the\s+)?second\s+one\b", re.IGNORECASE),
        re.compile(r"\b(?:no,?\s+)?not\s+that\s+one\b", re.IGNORECASE),
        re.compile(r"\b(?:no,?\s+)?(?:the\s+)?alternative\b", re.IGNORECASE),
    ]

    def __init__(self) -> None:
        # {task_id: list[VisualMemoryEntry]}
        self._buffers: dict[str, list[VisualMemoryEntry]] = {}
        # {task_id: current_turn_int}
        self._turn_counters: dict[str, int] = {}
        # {task_id: last_active_app_str}
        self._active_apps: dict[str, str] = {}
        # {task_id: GroundedTarget | None} (1-turn alternative slot for fast verbal correction)
        self._last_alternatives: dict[str, Optional[GroundedTarget]] = {}
        # {task_id: GroundedTarget | None} (cross-app transfer register for cross-app copy/upload/open handoff)
        self._cross_app_transfer_slot: dict[str, Optional[GroundedTarget]] = {}
        # {task_id: int} (turn at which cross-app transfer target was set)
        self._cross_app_transfer_turn: dict[str, int] = {}

    @classmethod
    def get_instance(cls) -> "VisualWorkingMemory":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    # ── Memory Ingestion ───────────────────────────────────────────────────────

    def remember(
        self,
        targets: list[GroundedTarget],
        task_id: str = "default",
        app_name: str = "",
    ) -> None:
        """
        Record grounded targets for the current focus task thread.
        Maintains ring buffer capacity and registers the second-highest confidence
        target in _last_alternatives for 1-turn correction.
        """
        if not targets:
            return

        with self._lock:
            if task_id not in self._buffers:
                self._buffers[task_id] = []
                self._turn_counters[task_id] = 0

            self._turn_counters[task_id] += 1
            current_turn = self._turn_counters[task_id]
            self._active_apps[task_id] = app_name.lower().strip()

            entry = VisualMemoryEntry(
                targets=targets,
                app_name=app_name.lower().strip(),
                turn_index=current_turn,
            )

            # Prepend to buffer & enforce max capacity
            self._buffers[task_id].insert(0, entry)
            if len(self._buffers[task_id]) > MAX_TARGETS_PER_THREAD:
                self._buffers[task_id] = self._buffers[task_id][:MAX_TARGETS_PER_THREAD]

            # If multiple targets returned, register 2nd-best into _last_alternatives slot
            if len(targets) > 1:
                # Sort descending by confidence
                sorted_targets = sorted(targets, key=lambda t: t.confidence, reverse=True)
                self._last_alternatives[task_id] = sorted_targets[1]
                best_t = sorted_targets[0]
                best_t.metadata["origin_app"] = app_name.lower().strip()
                self._cross_app_transfer_slot[task_id] = best_t
                self._cross_app_transfer_turn[task_id] = current_turn
            else:
                self._last_alternatives[task_id] = None
                best_t = targets[0]
                best_t.metadata["origin_app"] = app_name.lower().strip()
                self._cross_app_transfer_slot[task_id] = best_t
                self._cross_app_transfer_turn[task_id] = current_turn

            logger.debug(
                f"[VisualWorkingMemory] Remembered {len(targets)} target(s) for task '{task_id}' "
                f"in app '{app_name}' (turn={current_turn})."
            )

    # ── Referential & Correction Resolution ────────────────────────────────────

    def is_referential(self, text: str) -> bool:
        """Check whether the user utterance contains a referential or correction phrase."""
        txt = text.strip()
        for p in self.ALTERNATIVE_PATTERNS:
            if p.search(txt):
                return True
        for p in self.REFERENTIAL_PATTERNS:
            if p.search(txt):
                return True
        return False

    def is_alternative_correction(self, text: str) -> bool:
        """Check specifically for an alternative correction phrase ('no, the other one')."""
        txt = text.strip()
        for p in self.ALTERNATIVE_PATTERNS:
            if p.search(txt):
                return True
        return False

    CROSS_APP_VERBS = ("upload", "paste", "attach", "send", "transfer", "insert", "import")

    def resolve_reference(
        self,
        phrase: str,
        task_id: str = "default",
        current_app: str = "",
        allow_cross_app: bool = False,
    ) -> tuple[Optional[GroundedTarget], str]:
        """
        Resolve a pronoun or referential phrase to the best matching GroundedTarget.

        Returns:
          tuple[GroundedTarget | None, reason_or_type_str]
        """
        with self._lock:
            app_clean = current_app.lower().strip()
            phrase_lower = phrase.lower()

            # 1. Alternative correction fast-path ("no, the other one")
            if self.is_alternative_correction(phrase):
                alt = self._last_alternatives.get(task_id)
                if alt is not None:
                    # Check that alternative belongs to the same foreground app
                    if not app_clean or not alt.app_name or alt.app_name == app_clean:
                        logger.info(
                            f"[VisualWorkingMemory] Resolved alternative correction '{phrase}' -> "
                            f"'{alt.label}' (confidence={alt.confidence:.2f})"
                        )
                        # Consume the alternative slot
                        self._last_alternatives[task_id] = None
                        return alt, "alternative_correction"

            # Extract specific entity hint if present (e.g. "that file" -> "file", "that button" -> "button")
            entity_hint = ""
            for word in ("file", "folder", "button", "link", "window", "tab", "input", "field", "image", "document"):
                if word in phrase_lower:
                    entity_hint = word
                    break

            # 2. Referential ring-buffer lookup for intra-app targets
            buffer = self._buffers.get(task_id, [])
            current_turn = self._turn_counters.get(task_id, 0)

            best_target: Optional[GroundedTarget] = None
            best_score: float = -1.0

            for entry in buffer:
                # TTL check: evict stale entries older than DEFAULT_TTL_TURNS
                turn_delta = current_turn - entry.turn_index
                if turn_delta > DEFAULT_TTL_TURNS:
                    continue

                # App mismatch check: discount or skip targets from a different application
                is_same_app = (not app_clean) or (entry.app_name == app_clean)
                if not is_same_app:
                    continue

                recency_weight = 1.0 / (1.0 + turn_delta * 0.25)

                for target in entry.targets:
                    # Compute match score
                    type_boost = 1.2 if (entity_hint and entity_hint in target.label.lower()) else 1.0
                    score = target.confidence * recency_weight * type_boost

                    if score > best_score:
                        best_score = score
                        best_target = target

            if best_target is not None:
                logger.info(
                    f"[VisualWorkingMemory] Resolved referent '{phrase}' -> '{best_target.label}' "
                    f"(score={best_score:.2f}, source={best_target.source_tier})"
                )
                return best_target, "referential_match"

            # 3. Cross-app transfer resolution
            # Guard against false positives: Do NOT hijack intra-app commands like "insert a row", "paste", or "import os".
            # Cross-app transfer requires:
            #   a) allow_cross_app is explicitly enabled, OR
            #   b) The utterance combines a transfer action ("upload", "attach", "drop", "transfer", "send") with a
            #      deictic reference ("that", "it", "this", "the file", "the document", "the link") or explicit cross-app phrasing.
            has_deictic = any(d in phrase_lower.split() for d in ("that", "it", "this", "the", "those", "these"))
            has_transfer_verb = any(w in phrase_lower for w in ("upload", "attach", "drop", "transfer", "send"))
            has_explicit_cross = any(w in phrase_lower for w in ("from explorer", "into chrome", "to chat", "to ticket", "cross-app", "transfer to"))

            # Exclude non-transferable local operations like spreadsheet rows/columns or code imports
            incompatible_local_hints = {"row", "column", "cell", "sheet", "code", "variable", "function", "module", "library"}
            is_local_operation = any(lh in phrase_lower for lh in incompatible_local_hints)

            is_cross_intent = (
                allow_cross_app
                or (has_transfer_verb and has_deictic and not is_local_operation)
                or (has_explicit_cross and not is_local_operation)
            )

            if is_cross_intent:
                x_target = self._cross_app_transfer_slot.get(task_id)
                if x_target is not None:
                    x_turn = self._cross_app_transfer_turn.get(task_id, 0)
                    if current_turn - x_turn <= 3:
                        origin = x_target.metadata.get("origin_app", "")
                        # Verify entity compatibility
                        target_label_lower = x_target.label.lower()
                        valid_entity = (
                            not entity_hint
                            or entity_hint in target_label_lower
                            or (entity_hint in ("file", "folder", "document", "item", "attachment", "pdf", "image", "link")
                                and any(ext in target_label_lower for ext in (".", "file", "doc", "pdf", "xls", "csv", "txt", "png", "jpg", "http", "www", "folder")))
                        )
                        if valid_entity:
                            logger.info(
                                f"[VisualWorkingMemory] Resolved cross-app transfer '{phrase}' -> '{x_target.label}' "
                                f"(origin={origin}, confidence={x_target.confidence:.2f})"
                            )
                            return x_target, "cross_app_transfer"

            if not buffer:
                return None, "empty_memory"

            return None, "no_active_candidate"

    # ── App-Switch Decay ───────────────────────────────────────────────────────

    def decay_on_app_switch(
        self,
        previous_app: str,
        new_app: str,
        task_id: str = "default",
    ) -> None:
        """
        Decay or invalidate memory entries when the foreground window switches,
        preventing 'that file' in Explorer from leaking into VS Code or Chrome,
        while preserving the most recent high-confidence target in the cross-app
        transfer register for explicit cross-app handoffs.
        """
        prev = previous_app.lower().strip()
        new = new_app.lower().strip()

        if prev == new or not new:
            return

        with self._lock:
            # Invalidate the 1-turn alternative slot
            self._last_alternatives[task_id] = None
            self._active_apps[task_id] = new

            buffer = self._buffers.get(task_id, [])

            # Preserve the most recent high-confidence target from previous app into transfer slot
            prev_targets = []
            for entry in buffer:
                if entry.app_name == prev:
                    prev_targets.extend(entry.targets)
            if prev_targets:
                best_prev = max(prev_targets, key=lambda t: t.confidence)
                if best_prev.confidence >= 0.70:
                    import copy
                    x_target = copy.deepcopy(best_prev)
                    x_target.confidence = max(0.75, x_target.confidence * 0.85)
                    x_target.metadata["origin_app"] = prev
                    self._cross_app_transfer_slot[task_id] = x_target
                    self._cross_app_transfer_turn[task_id] = self._turn_counters.get(task_id, 0)

            # Filter out entries from the previous app or apply heavy confidence penalty
            retained = []
            for entry in buffer:
                if entry.app_name == prev:
                    # Heavily penalize confidence on app switch
                    for t in entry.targets:
                        t.confidence *= 0.20
                if any(t.confidence >= 0.40 for t in entry.targets):
                    retained.append(entry)

            self._buffers[task_id] = retained
            logger.debug(
                f"[VisualWorkingMemory] Applied app-switch decay '{prev}' -> '{new}' "
                f"for task '{task_id}'. Retained {len(retained)} entry(ies)."
            )

    # ── Cross-App Transfer Helpers ─────────────────────────────────────────────

    def get_cross_app_transfer(self, task_id: str = "default") -> Optional[GroundedTarget]:
        """Retrieve current cross-app transferable target if available."""
        with self._lock:
            return self._cross_app_transfer_slot.get(task_id)

    def set_cross_app_transfer(
        self,
        target: GroundedTarget,
        task_id: str = "default",
        origin_app: str = "",
    ) -> None:
        """Explicitly register a target into the cross-app transfer register."""
        with self._lock:
            import copy
            t = copy.deepcopy(target)
            if origin_app:
                t.metadata["origin_app"] = origin_app.lower().strip()
            self._cross_app_transfer_slot[task_id] = t
            self._cross_app_transfer_turn[task_id] = self._turn_counters.get(task_id, 0)
