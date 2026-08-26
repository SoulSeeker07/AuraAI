"""
External Memory Importer — Base ABC
Location: src/memory/importers/base_importer.py

Abstract base class for importing memory facts from external AI assistant
exports (Claude, ChatGPT) into AuraAI's CognitiveMemoryEngine.

Design decisions:
- Imports target CognitiveMemoryEngine (SQLite/Path 2), NOT LongTermMemory (Chroma/Path 1).
- MemoryItem.importance is a 0.0-1.0 float on this path (matching DecayEngine's scale).
- apply_policy() is reused for Gates 1-2 (hard-exclusion, sensitive-info regex) only.
  Gate 3 (importance >= 3 on a 1-5 int scale) is irrelevant on this path and bypassed
  by hardcoding importance=5 in the adapter call. See check_policy_gates() docstring.
- Each import batch generates a unique batch_id. Every written fact is tagged with it
  in metadata["import_batch_id"] to enable future rollback-by-batch.
- Conflict detection flags semantically overlapping facts as PendingConfirmation
  (metadata["pending_confirmation"]=True, confidence=0.0) instead of silently overwriting.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memory.cognitive_memory import CognitiveMemoryEngine

from memory.manager.memory_policy import apply_policy
from memory.models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

IMPORTED_DEFAULT_IMPORTANCE: float = 0.50
"""Below session-observed facts (0.7-0.85), well below the 0.9 permanent-safeguard zone."""

IMPORTED_DEFAULT_CONFIDENCE: float = 0.60
"""Below natively-observed confidence (0.95). Promotable via re-confirmation."""


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RawMemoryFact:
    """
    Vendor-agnostic normalized shape for a single imported memory fact.
    Both Claude and ChatGPT export formats are coerced into this before
    classification and storage.
    """

    text: str
    category_hint: str = ""
    timestamp: str = ""
    source: str = ""
    original_key: str = ""


@dataclass
class ImportResult:
    """Summary of an import operation. Returned by import_to_memory()."""

    batch_id: str
    imported_count: int = 0
    skipped_count: int = 0
    conflict_count: int = 0
    pending_count: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Policy adapter
# ---------------------------------------------------------------------------

def check_policy_gates(fact_text: str, topic: str) -> tuple[bool, str]:
    """
    Run apply_policy() for its hard-exclusion (Gate 1) and sensitive-info (Gate 2)
    regex checks only. Gate 3 (importance >= 3 on a 1-5 int scale) is irrelevant
    on the CognitiveMemoryEngine path, which uses 0.0-1.0 floats for importance.

    importance=5 is hardcoded to unconditionally clear Gate 3 so that only
    Gates 1 and 2 can reject. This is intentional — the 1-5 int scale belongs
    to the LongTermMemory/Chroma path (Path 1) and has no meaning here.

    Returns:
        (passed: bool, reason: str)
    """
    verdict = apply_policy({"fact": fact_text, "topic": topic, "importance": 5})
    return verdict.store, verdict.reason


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------

class ExternalMemoryImporter(ABC):
    """
    Abstract base for vendor-specific memory import adapters.

    Subclasses implement parse() to read a vendor's export format.
    import_to_memory() is the concrete template method that handles
    classification, policy gating, conflict detection, and storage.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Vendor identifier: 'claude' or 'chatgpt'."""
        ...

    @property
    @abstractmethod
    def provenance_source(self) -> ProvenanceSource:
        """ProvenanceSource enum value for this vendor."""
        ...

    @abstractmethod
    def parse(self, export_path: str) -> list[RawMemoryFact]:
        """
        Read the vendor export format and return normalized raw facts.

        Args:
            export_path: Path to a .zip file or extracted directory.

        Returns:
            List of RawMemoryFact, one per importable memory entry.
        """
        ...

    def import_to_memory(
        self,
        export_path: str,
        cognitive_engine: CognitiveMemoryEngine,
        dry_run: bool = False,
    ) -> ImportResult:
        """
        Template method: parse → classify → gate → conflict-check → store.

        Args:
            export_path: Path to vendor export file or directory.
            cognitive_engine: The CognitiveMemoryEngine instance to write to.
            dry_run: If True, run the full pipeline but skip actual DB writes.
                     Returns accurate counts of what would happen.

        Returns:
            ImportResult with counts and batch_id.
        """
        from .schema_mapper import SchemaMapper

        batch_id = f"import_{self.source_name}_{uuid.uuid4().hex[:8]}"
        result = ImportResult(batch_id=batch_id)
        mapper = SchemaMapper()

        try:
            raw_facts = self.parse(export_path)
        except Exception as exc:
            logger.error(f"[{self.source_name}] Parse failed: {exc}", exc_info=True)
            result.errors.append(f"parse_error: {exc}")
            return result

        logger.info(
            f"[{self.source_name}] Parsed {len(raw_facts)} raw facts from '{export_path}'"
            f" (batch={batch_id}, dry_run={dry_run})"
        )

        now_iso = dt.datetime.now().isoformat(timespec="seconds")

        for fact in raw_facts:
            # Gate 1-2: hard-exclusion + sensitive-info policy check
            passed, reason = check_policy_gates(fact.text, fact.category_hint)
            if not passed:
                logger.debug(f"[{self.source_name}] Policy rejected: {fact.text!r} — {reason}")
                result.skipped_count += 1
                continue

            # Classify into MemoryType and topic
            mem_type = mapper.classify_store(fact)
            topic = mapper.classify_topic(fact)

            # Conflict detection
            is_conflict = mapper.check_conflict(fact, cognitive_engine)

            # Build MemoryItem
            memory = MemoryItem(
                content=fact.text,
                type=mem_type,
                provenance=MemoryProvenance(
                    source_type=self.provenance_source,
                    source_id=f"{self.source_name}_import",
                    confidence=IMPORTED_DEFAULT_CONFIDENCE,
                    verified=False,
                ),
                importance=IMPORTED_DEFAULT_IMPORTANCE,
                confidence=0.0 if is_conflict else IMPORTED_DEFAULT_CONFIDENCE,
                project_id="global",
                topic=topic,
                created_at=fact.timestamp or now_iso,
                metadata={
                    "import_batch_id": batch_id,
                    "import_source": self.source_name,
                    "original_key": fact.original_key,
                    "category_hint": fact.category_hint,
                    "pending_confirmation": is_conflict,
                    "imported_at": now_iso,
                },
            )

            if is_conflict:
                result.conflict_count += 1
                result.pending_count += 1
                logger.info(
                    f"[{self.source_name}] Conflict detected, flagged as PendingConfirmation: "
                    f"{fact.text[:60]!r}"
                )

            if not dry_run:
                cognitive_engine.store_memory(memory)

            result.imported_count += 1

        logger.info(
            f"[{self.source_name}] Import {'preview' if dry_run else 'complete'}: "
            f"batch={batch_id}, imported={result.imported_count}, "
            f"skipped={result.skipped_count}, conflicts={result.conflict_count}, "
            f"pending={result.pending_count}"
        )

        return result
