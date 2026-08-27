"""
browser/experience_store.py
===========================
Episodic Memory Layer for Autonomous Web Agent.
Stores and retrieves verified task traces (domain, goal, action sequence, selectors,
success status, and confidence score) directly in the existing Chroma vector store
under the 'browser_experience' collection namespace.

Design Principles:
- Reuses existing LongTermMemory Chroma database directory (`./aura_memory_db`).
- Treat retrieved traces ONLY as candidate hypotheses (hints to prime the reasoning stage).
- NEVER bypass Observe / Verify stages in the closed-loop agent execution.
- Includes staleness invalidation: discounts confidence or expires traces when DOM structures change.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("AURA_MEMORY_DB_PATH", "./aura_memory_db")


class BrowserExperienceStore:
    _instance: Optional["BrowserExperienceStore"] = None

    def __init__(self, persist_dir: str = DB_PATH):
        self.persist_dir = persist_dir
        self._collection = None
        self._embedder = None
        self._init_store()

    @classmethod
    def get_instance(cls) -> "BrowserExperienceStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_store(self) -> None:
        try:
            import chromadb
            client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = client.get_or_create_collection("browser_experience")
            logger.info("[BrowserExperienceStore] Connected to 'browser_experience' collection at %s", self.persist_dir)
        except Exception as e:
            logger.warning("[BrowserExperienceStore] Chroma initialization notice: %s. Using memory fallback.", e)
            self._collection = None

    def _extract_domain(self, url_or_goal: str) -> str:
        """Extract clean domain name from URL or goal text."""
        if not url_or_goal:
            return "general"
        for part in url_or_goal.split():
            if "://" in part or part.startswith("www.") or any(part.endswith(ext) for ext in (".com", ".in", ".org", ".net")):
                try:
                    parsed = urlparse(part if "://" in part else f"https://{part}")
                    return parsed.netloc.lower().replace("www.", "")
                except Exception:
                    pass
        for site in ("flipkart", "amazon", "google", "youtube", "github", "wikipedia", "reddit", "twitter", "myntra"):
            if site in url_or_goal.lower():
                return f"{site}.com"
        return "general"

    def record_trace(
        self,
        domain: str,
        goal: str,
        action_sequence: List[Dict[str, Any]],
        selectors_used: List[str],
        success: bool = True,
        confidence: float = 1.0,
        summary: str = "",
    ) -> str:
        """
        Persist a verified task trace to episodic memory.
        """
        if not self._collection or not action_sequence:
            return ""

        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        timestamp = time.time()
        dom = domain or self._extract_domain(goal)

        # Build search document representation
        document_text = f"Domain: {dom} | Goal: {goal} | Actions: {len(action_sequence)} | Summary: {summary}"

        metadata = {
            "trace_id": trace_id,
            "domain": dom,
            "goal": goal[:200],
            "action_count": len(action_sequence),
            "success": str(success),
            "confidence": float(confidence),
            "timestamp": timestamp,
            "summary": summary[:300],
            "action_sequence_json": json.dumps(action_sequence[:15]),
            "selectors_json": json.dumps(selectors_used[:10]),
        }

        try:
            if self._embedder is not None:
                # CRITICAL: normalize_embeddings=True ensures unit length vectors (|v|=1) for accurate cosine/L2 composite ranking.
                # If embedding model or normalization changes, the entire Chroma collection must be purged/re-embedded.
                vec = self._embedder.encode(document_text, normalize_embeddings=True).tolist()
                self._collection.add(
                    ids=[trace_id],
                    embeddings=[vec],
                    documents=[document_text],
                    metadatas=[metadata],
                )
            else:
                self._collection.add(
                    ids=[trace_id],
                    documents=[document_text],
                    metadatas=[metadata],
                )
            logger.info("[BrowserExperienceStore] Saved verified trace %s (domain=%s, confidence=%.2f)", trace_id, dom, confidence)
            return trace_id
        except Exception as ex:
            logger.debug("[BrowserExperienceStore] Failed to record trace: %s", ex)
            return ""

    def retrieve_trace(
        self,
        domain: str,
        goal: str,
        min_confidence: float = 0.5,
        top_k: int = 1,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve the most relevant past verified trace as a candidate hypothesis.
        """
        if not self._collection:
            return None

        query_text = f"Domain: {domain} | Goal: {goal}"
        dom = domain or self._extract_domain(goal)

        try:
            where = {"domain": dom} if dom and dom != "general" else None
            pool_size = min(max(top_k * 5, 5), 20)
            if self._embedder is not None:
                vec = self._embedder.encode(query_text, normalize_embeddings=True).tolist()
                results = self._collection.query(
                    query_embeddings=[vec],
                    n_results=pool_size,
                    where=where,
                    include=["metadatas", "distances"],
                )
            else:
                results = self._collection.query(
                    query_texts=[query_text],
                    n_results=pool_size,
                    where=where,
                    include=["metadatas", "distances"],
                )

            if not results or not results.get("ids") or not results["ids"][0]:
                return None

            candidates = []
            ids = results["ids"][0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0] if results.get("distances") else [0.0] * len(ids)

            for i, trace_id in enumerate(ids):
                meta = metadatas[i] if i < len(metadatas) else {}
                dist = distances[i] if i < len(distances) else 0.0
                conf = float(meta.get("confidence", 1.0))
                
                if conf < min_confidence:
                    continue

                # Similarity score in [0.0, 1.0] from distance
                sim = 1.0 / (1.0 + dist)
                composite_score = sim * conf

                try:
                    action_sequence = json.loads(meta.get("action_sequence_json", "[]"))
                except Exception:
                    action_sequence = []

                try:
                    selectors_used = json.loads(meta.get("selectors_json", "[]"))
                except Exception:
                    selectors_used = []

                candidates.append({
                    "trace_id": trace_id,
                    "domain": meta.get("domain", ""),
                    "goal": meta.get("goal", ""),
                    "action_sequence": action_sequence,
                    "selectors_used": selectors_used,
                    "confidence": conf,
                    "summary": meta.get("summary", ""),
                    "timestamp": float(meta.get("timestamp", 0.0)),
                    "composite_score": composite_score,
                })

            if not candidates:
                return None

            # Sort descending by composite score (similarity * confidence)
            candidates.sort(key=lambda c: c["composite_score"], reverse=True)
            best = candidates[0]
            return {
                "trace_id": best["trace_id"],
                "domain": best["domain"],
                "goal": best["goal"],
                "action_sequence": best["action_sequence"],
                "selectors_used": best["selectors_used"],
                "selectors": best["selectors_used"],
                "confidence": best["confidence"],
                "summary": best["summary"],
                "timestamp": best["timestamp"],
            }
        except Exception as ex:
            logger.debug("[BrowserExperienceStore] Trace retrieval error: %s", ex)
            return None

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a specific trace by ID."""
        if not self._collection:
            return None
        try:
            results = self._collection.get(ids=[trace_id], include=["metadatas"])
            if not results or not results.get("ids") or not results["ids"]:
                return None
            meta = results["metadatas"][0]
            try:
                action_sequence = json.loads(meta.get("action_sequence_json", "[]"))
            except Exception:
                action_sequence = []
            try:
                selectors_used = json.loads(meta.get("selectors_json", "[]"))
            except Exception:
                selectors_used = []
            return {
                "trace_id": trace_id,
                "domain": meta.get("domain", ""),
                "goal": meta.get("goal", ""),
                "action_sequence": action_sequence,
                "selectors_used": selectors_used,
                "selectors": selectors_used,
                "confidence": float(meta.get("confidence", 1.0)),
                "summary": meta.get("summary", ""),
                "timestamp": float(meta.get("timestamp", 0.0)),
            }
        except Exception as ex:
            logger.debug("[BrowserExperienceStore] Get trace error: %s", ex)
            return None

    def purge_domain(self, domain: str) -> int:
        """Purge all stored traces for a specific domain (useful for test resets)."""
        if not self._collection:
            return 0
        try:
            dom = domain.lower().replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
            results = self._collection.get(where={"domain": dom})
            ids_to_del = results.get("ids", []) if results else []
            if ids_to_del:
                self._collection.delete(ids=ids_to_del)
                logger.info("[BrowserExperienceStore] Purged %d traces for domain '%s'", len(ids_to_del), dom)
            return len(ids_to_del)
        except Exception as ex:
            logger.debug("[BrowserExperienceStore] Purge domain error: %s", ex)
            return 0

    def discount_trace(
        self,
        trace_id: str,
        penalty: Optional[float] = None,
        failure_type: str = "hard",
        reason: str = "",
    ) -> None:
        """
        Staleness Invalidation: Discount confidence score when verification or DOM selector fails.
        Tiered policy:
        - Hard structural failure (selector missing / element detached): penalty = 0.50
        - Soft interaction mismatch / timeout: penalty = 0.25
        """
        if not self._collection or not trace_id:
            return

        effective_penalty = penalty if penalty is not None else (0.50 if failure_type == "hard" else 0.25)

        try:
            existing = self._collection.get(ids=[trace_id])
            if not existing or not existing.get("metadatas") or not existing["metadatas"]:
                return

            metadata = dict(existing["metadatas"][0])
            current_conf = float(metadata.get("confidence", 1.0))
            new_conf = max(0.0, current_conf - effective_penalty)

            if new_conf < 0.25:
                # Expire stale trace completely
                self._collection.delete(ids=[trace_id])
                logger.info(
                    "[BrowserExperienceStore] EXPIRED trace_id=%s reason='%s' penalty=%.2f old_conf=%.2f new_conf=%.2f (dropped below 0.25)",
                    trace_id, reason, effective_penalty, current_conf, new_conf
                )
            else:
                metadata["confidence"] = new_conf
                self._collection.update(ids=[trace_id], metadatas=[metadata])
                logger.info(
                    "[BrowserExperienceStore] DISCOUNT trace_id=%s reason='%s' penalty=%.2f old_conf=%.2f new_conf=%.2f",
                    trace_id, reason, effective_penalty, current_conf, new_conf
                )
        except Exception as ex:
            logger.debug("[BrowserExperienceStore] Failed to discount trace %s: %s", trace_id, ex)
