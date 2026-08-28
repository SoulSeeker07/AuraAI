"""
Memory Consolidation Task — "Auto Dream"
Location: src/memory/consolidation_task.py

Periodic background task that re-reads CognitiveMemoryEngine's stores,
deduplicates near-identical facts, prunes expired entries, and promotes
confidence of imported facts that have been re-confirmed by session observations.

Design decisions:
- Dedup uses embedding cosine similarity (reuses LongTermMemory's SentenceTransformer)
  with fallback to difflib.SequenceMatcher when embedder is unavailable.
- Prune delegates to DecayEngine.is_expired() — skips audit_exempt entries.
- Confidence promotion: +0.10 per re-confirmation, capped at 0.95, idempotent per session.
- Audit log stored at importance=1.0 (triggers the >= 0.9 permanent-safeguard branch
  of DecayEngine's OR guard), with metadata["audit_exempt"]=True to prevent the
  consolidation task from deduping/pruning its own logs.
- dry_run mode returns a ConsolidationReport without modifying any data.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from memory.cognitive_memory import CognitiveMemoryEngine

from memory.decay_engine import DecayEngine
from memory.models import MemoryItem, MemoryProvenance, MemoryType, ProvenanceSource

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

EMBEDDING_DEDUP_THRESHOLD: float = 0.88
"""Cosine similarity threshold for embedding-based dedup (primary path)."""

LEXICAL_DEDUP_THRESHOLD: float = 0.92
"""SequenceMatcher ratio threshold for lexical dedup (fallback when embedder unavailable)."""

CONFIRMATION_BOOST: float = 0.10
"""Confidence increase per re-confirmation of an imported fact."""

CONFIDENCE_CEILING: float = 0.95
"""Maximum confidence reachable via automated promotion. 1.0 is reserved for USER_EXPLICIT."""

# Provenance sources that are eligible for confidence promotion
_IMPORTED_SOURCES: frozenset[str] = frozenset({
    ProvenanceSource.IMPORTED.value,
    ProvenanceSource.CLAUDE_IMPORT.value,
    ProvenanceSource.CHATGPT_IMPORT.value,
})


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class ConsolidationReport:
    """Summary of a consolidation run."""

    deduped_count: int = 0
    pruned_count: int = 0
    promoted_count: int = 0
    skipped_audit_count: int = 0
    total_scanned: int = 0
    dry_run: bool = False
    errors: list[str] = field(default_factory=list)
    deduped_pairs: list[tuple[str, str]] = field(default_factory=list)
    pruned_ids: list[str] = field(default_factory=list)
    promoted_ids: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class MemoryConsolidationTask:
    """
    Auto-Dream consolidation: dedup, prune, promote across all memory stores.

    Usage:
        task = MemoryConsolidationTask()
        report = task.run(cognitive_engine, dry_run=True)  # preview
        report = task.run(cognitive_engine, dry_run=False)  # execute
    """

    def __init__(self) -> None:
        self._decay_engine = DecayEngine()
        self._embedder: Any = None
        self._embedder_loaded = False

    def _get_embedder(self) -> Any:
        """
        Lazy-load the SentenceTransformer embedder from VectorMemoryEngine.
        Reuses the process-wide singleton — does NOT load a duplicate model.
        Falls back to None if unavailable.
        """
        if not self._embedder_loaded:
            self._embedder_loaded = True
            try:
                from memory.vector_memory import VectorMemoryEngine
                engine = VectorMemoryEngine.get_instance()
                self._embedder = engine.get_model()
                if self._embedder is not None:
                    logger.info("[ConsolidationTask] Reusing VectorMemoryEngine embedding model for dedup")
            except Exception as exc:
                logger.warning(
                    f"[ConsolidationTask] Embedding model unavailable, "
                    f"falling back to lexical dedup: {exc}"
                )
                self._embedder = None
        return self._embedder

    def run(
        self,
        cognitive_engine: CognitiveMemoryEngine,
        dry_run: bool = False,
    ) -> ConsolidationReport:
        """
        Execute the consolidation pipeline.

        1. Load all memories from CognitiveMemoryEngine
        2. Dedup near-identical facts within the same MemoryType
        3. Prune expired facts (via DecayEngine)
        4. Promote imported facts that have been re-confirmed
        5. Write audit log entry

        Args:
            cognitive_engine: The CognitiveMemoryEngine instance.
            dry_run: If True, compute the report without modifying data.

        Returns:
            ConsolidationReport with counts and details.
        """
        report = ConsolidationReport(dry_run=dry_run)

        try:
            # Load all memories (including expired items so they can be pruned)
            try:
                all_memories = cognitive_engine.search_memories(query="", limit=500, include_expired=True)
            except TypeError:
                all_memories = cognitive_engine.search_memories(query="", limit=500)
            report.total_scanned = len(all_memories)

            if not all_memories:
                logger.info("[ConsolidationTask] No memories to consolidate.")
                return report

            # Separate audit-exempt entries
            regular: list[MemoryItem] = []
            for mem in all_memories:
                if mem.metadata.get("audit_exempt"):
                    report.skipped_audit_count += 1
                else:
                    regular.append(mem)

            # Phase 1: Dedup
            merged_ids = self._dedup(regular, cognitive_engine, report, dry_run)
            surviving_after_dedup = [m for m in regular if m.memory_id not in merged_ids]

            # Phase 2: Prune
            pruned_ids = self._prune(surviving_after_dedup, cognitive_engine, report, dry_run)
            surviving_after_prune = [m for m in surviving_after_dedup if m.memory_id not in pruned_ids]

            # Phase 3: Promote imported facts (only active, surviving memories)
            self._promote(surviving_after_prune, cognitive_engine, report, dry_run)

            # Phase 4: Write audit log
            if not dry_run:
                self._write_audit_log(cognitive_engine, report)

        except Exception as exc:
            logger.error(f"[ConsolidationTask] Failed: {exc}", exc_info=True)
            report.errors.append(f"consolidation_error: {exc}")

        logger.info(
            f"[ConsolidationTask] {'Preview' if dry_run else 'Complete'}: "
            f"scanned={report.total_scanned}, deduped={report.deduped_count}, "
            f"pruned={report.pruned_count}, promoted={report.promoted_count}, "
            f"audit_skipped={report.skipped_audit_count}"
        )

        return report

    # -----------------------------------------------------------------------
    # Phase 1: Dedup
    # -----------------------------------------------------------------------

    def _dedup(
        self,
        memories: list[MemoryItem],
        engine: CognitiveMemoryEngine,
        report: ConsolidationReport,
        dry_run: bool,
    ) -> set[str]:
        """Find and merge near-identical facts within the same MemoryType."""
        # Group by type
        by_type: dict[MemoryType, list[MemoryItem]] = {}
        for mem in memories:
            by_type.setdefault(mem.type, []).append(mem)

        embedder = self._get_embedder()
        merged_ids: set[str] = set()

        for mem_type, group in by_type.items():
            if len(group) < 2:
                continue

            if embedder is not None:
                self._dedup_embedding(group, embedder, engine, report, dry_run, merged_ids)
            else:
                self._dedup_lexical(group, engine, report, dry_run, merged_ids)

        return merged_ids

    def _dedup_embedding(
        self,
        group: list[MemoryItem],
        embedder: Any,
        engine: CognitiveMemoryEngine,
        report: ConsolidationReport,
        dry_run: bool,
        merged_ids: set[str],
    ) -> None:
        """Embedding-based dedup using cosine similarity."""
        texts = [m.content for m in group]
        try:
            embeddings = embedder.encode(texts, show_progress_bar=False)
            # Normalize for cosine similarity
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1, norms)
            normalized = embeddings / norms
        except Exception as exc:
            logger.warning(f"[ConsolidationTask] Embedding dedup failed, skipping: {exc}")
            return

        for i in range(len(group)):
            if group[i].memory_id in merged_ids:
                continue
            for j in range(i + 1, len(group)):
                if group[j].memory_id in merged_ids:
                    continue

                similarity = float(np.dot(normalized[i], normalized[j]))
                if similarity >= EMBEDDING_DEDUP_THRESHOLD:
                    self._merge_pair(
                        group[i], group[j], engine, report, dry_run, merged_ids
                    )

    def _dedup_lexical(
        self,
        group: list[MemoryItem],
        engine: CognitiveMemoryEngine,
        report: ConsolidationReport,
        dry_run: bool,
        merged_ids: set[str],
    ) -> None:
        """Lexical dedup fallback using SequenceMatcher."""
        logger.debug("[ConsolidationTask] Using lexical dedup (embedder unavailable)")

        for i in range(len(group)):
            if group[i].memory_id in merged_ids:
                continue
            for j in range(i + 1, len(group)):
                if group[j].memory_id in merged_ids:
                    continue

                ratio = SequenceMatcher(
                    None, group[i].content, group[j].content
                ).ratio()
                if ratio >= LEXICAL_DEDUP_THRESHOLD:
                    self._merge_pair(
                        group[i], group[j], engine, report, dry_run, merged_ids
                    )

    def _merge_pair(
        self,
        keep: MemoryItem,
        discard: MemoryItem,
        engine: CognitiveMemoryEngine,
        report: ConsolidationReport,
        dry_run: bool,
        merged_ids: set[str],
    ) -> None:
        """
        Merge two duplicate memories with deterministic tie-breaking:
        1. Higher confidence wins
        2. On tie: Native/observed provenance wins over imported provenance
        3. On tie: Higher importance wins
        4. On tie: Higher access count wins
        """
        # Deterministic ranking order:
        # 1. Higher confidence wins
        # 2. Native/observed provenance wins over imported provenance
        # 3. Higher importance wins
        # 4. Higher access count wins
        # 5. Earliest created_at wins (oldest record takes precedence)
        # 6. Lexicographical memory_id as absolute deterministic tiebreaker
        keep_score = (
            keep.confidence,
            0 if self._is_imported(keep) else 1,
            keep.importance,
            keep.access_count,
            -(dt.datetime.fromisoformat(keep.created_at).timestamp() if keep.created_at else 0),
            keep.memory_id,
        )
        discard_score = (
            discard.confidence,
            0 if self._is_imported(discard) else 1,
            discard.importance,
            discard.access_count,
            -(dt.datetime.fromisoformat(discard.created_at).timestamp() if discard.created_at else 0),
            discard.memory_id,
        )
        if discard_score > keep_score:
            keep, discard = discard, keep

        report.deduped_count += 1
        report.deduped_pairs.append((keep.memory_id, discard.memory_id))
        merged_ids.add(discard.memory_id)

        if not dry_run:
            # Update the kept entry: combine access counts and metadata
            keep.access_count += discard.access_count
            merged_meta = {**discard.metadata, **keep.metadata}
            # Guardrail: Never let a discarded import batch tag contaminate a native memory
            if not self._is_imported(keep):
                merged_meta.pop("import_batch_id", None)
                merged_meta.pop("import_source", None)
            merged_meta["merged_from"] = discard.memory_id
            keep.metadata = merged_meta
            engine.store_memory(keep)

            # Delete the discarded entry
            self._delete_memory(engine, discard.memory_id)

        logger.debug(
            f"[ConsolidationTask] Merged: keep={keep.memory_id}, discard={discard.memory_id}"
        )

    # -----------------------------------------------------------------------
    # Phase 2: Prune
    # -----------------------------------------------------------------------

    def _prune(
        self,
        memories: list[MemoryItem],
        engine: CognitiveMemoryEngine,
        report: ConsolidationReport,
        dry_run: bool,
    ) -> set[str]:
        """Remove expired memories via DecayEngine."""
        now = dt.datetime.now()
        pruned_ids: set[str] = set()
        for mem in memories:
            # Skip PendingConfirmation — user hasn't reviewed yet
            if mem.metadata.get("pending_confirmation"):
                continue

            if self._decay_engine.is_expired(mem, now):
                report.pruned_count += 1
                report.pruned_ids.append(mem.memory_id)
                pruned_ids.add(mem.memory_id)

                if not dry_run:
                    self._delete_memory(engine, mem.memory_id)

                logger.debug(f"[ConsolidationTask] Pruned expired: {mem.memory_id}")

        return pruned_ids

    # -----------------------------------------------------------------------
    # Phase 3: Promote
    # -----------------------------------------------------------------------

    def _promote(
        self,
        memories: list[MemoryItem],
        engine: CognitiveMemoryEngine,
        report: ConsolidationReport,
        dry_run: bool,
    ) -> None:
        """
        Promote confidence of imported facts that have been re-confirmed.

        A fact is considered "re-confirmed" if a non-imported memory with
        high keyword overlap exists in the same store (suggesting the user
        or session independently corroborated the imported fact).

        Formula: new_confidence = min(0.95, current + 0.10)
        Idempotent per consolidation run.
        """
        imported = [
            m for m in memories
            if self._is_imported(m) and m.confidence < CONFIDENCE_CEILING
        ]
        observed = [m for m in memories if not self._is_imported(m)]

        if not imported or not observed:
            return

        for imp in imported:
            imp_tokens = _tokenize(imp.content)
            if not imp_tokens:
                continue

            # Check if any observed fact corroborates this imported fact
            for obs in observed:
                obs_tokens = _tokenize(obs.content)
                if not obs_tokens:
                    continue

                shared = imp_tokens & obs_tokens
                overlap = len(shared) / max(1, len(imp_tokens))
                if len(shared) >= 2 and overlap >= 0.25:  # Corroborated by session observation
                    new_confidence = min(
                        CONFIDENCE_CEILING,
                        imp.confidence + CONFIRMATION_BOOST,
                    )
                    if new_confidence > imp.confidence:
                        report.promoted_count += 1
                        report.promoted_ids.append(imp.memory_id)

                        if not dry_run:
                            imp.confidence = new_confidence
                            imp.metadata["last_promoted_at"] = (
                                dt.datetime.now().isoformat(timespec="seconds")
                            )
                            engine.store_memory(imp)

                        logger.debug(
                            f"[ConsolidationTask] Promoted {imp.memory_id}: "
                            f"confidence {imp.confidence:.2f} → {new_confidence:.2f}"
                        )
                    break  # Only one boost per consolidation run (idempotent)

    # -----------------------------------------------------------------------
    # Phase 4: Audit log
    # -----------------------------------------------------------------------

    def _write_audit_log(
        self,
        engine: CognitiveMemoryEngine,
        report: ConsolidationReport,
    ) -> None:
        """
        Write a consolidation audit log entry.

        Stored at importance=1.0 (triggers the >= 0.9 permanent-safeguard branch
        in DecayEngine, preventing this entry from ever being pruned or decayed).
        metadata["audit_exempt"]=True prevents the consolidation task from
        deduping/pruning its own log entries in future runs.
        """
        now_iso = dt.datetime.now().isoformat(timespec="seconds")
        log_content = (
            f"Consolidation run at {now_iso}: "
            f"scanned={report.total_scanned}, "
            f"deduped={report.deduped_count}, "
            f"pruned={report.pruned_count}, "
            f"promoted={report.promoted_count}"
        )

        audit_entry = MemoryItem(
            type=MemoryType.EPISODIC,
            content=log_content,
            importance=1.0,  # Permanent safeguard: importance >= 0.9 → never expires
            confidence=1.0,
            project_id="global",
            topic="audit:consolidation",
            provenance=MemoryProvenance(
                source_type=ProvenanceSource.RUNTIME_SESSION,
                source_id="consolidation_task",
                confidence=1.0,
                verified=True,
            ),
            metadata={
                "audit_exempt": True,
                "deduped_count": report.deduped_count,
                "pruned_count": report.pruned_count,
                "promoted_count": report.promoted_count,
                "total_scanned": report.total_scanned,
                "deduped_pairs": report.deduped_pairs[:20],  # Cap for storage
                "pruned_ids": report.pruned_ids[:20],
                "promoted_ids": report.promoted_ids[:20],
                "run_timestamp": now_iso,
            },
        )
        engine.store_memory(audit_entry)
        logger.info(f"[ConsolidationTask] Audit log written: {log_content}")

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _is_imported(mem: MemoryItem) -> bool:
        """Check if a memory was created via external import."""
        prov_source = ""
        if hasattr(mem.provenance, "source_type"):
            prov_source = (
                mem.provenance.source_type.value
                if hasattr(mem.provenance.source_type, "value")
                else str(mem.provenance.source_type)
            )
        return prov_source in _IMPORTED_SOURCES

    @staticmethod
    def _delete_memory(engine: CognitiveMemoryEngine, memory_id: str) -> None:
        """Delete a memory from the cognitive engine's SQLite store."""
        try:
            with engine._connect() as conn:
                conn.execute(
                    "DELETE FROM cognitive_memories WHERE memory_id = ?",
                    (memory_id,),
                )
            logger.debug(f"[ConsolidationTask] Deleted memory: {memory_id}")
        except Exception as exc:
            logger.warning(f"[ConsolidationTask] Delete failed for {memory_id}: {exc}")


def _tokenize(text: str) -> set[str]:
    """Tokenize text into a set of lowercase words (length > 2)."""
    import re
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}
