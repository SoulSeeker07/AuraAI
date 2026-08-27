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
            import torch
            from sentence_transformers import SentenceTransformer
            dev = "cuda" if torch.cuda.is_available() else "cpu"
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2", device=dev, local_files_only=True)
        except Exception as e:
            logger.debug("[BrowserExperienceStore] Local embedding model notice: %s", e)
            self._embedder = None

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
                vec = self._embedder.encode(document_text).tolist()
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
            if self._embedder is not None:
                vec = self._embedder.encode(query_text).tolist()
                results = self._collection.query(
                    query_embeddings=[vec],
                    n_results=top_k,
                    where=where,
                )
            else:
                results = self._collection.query(
                    query_texts=[query_text],
                    n_results=top_k,
                    where=where,
                )

            if not results or not results.get("ids") or not results["ids"][0]:
                return None

            metadata = results["metadatas"][0][0]
            confidence = float(metadata.get("confidence", 0.0))
            if confidence < min_confidence or metadata.get("success") != "True":
                return None

            actions = json.loads(metadata.get("action_sequence_json", "[]"))
            selectors = json.loads(metadata.get("selectors_json", "[]"))

            return {
                "trace_id": metadata.get("trace_id"),
                "domain": metadata.get("domain"),
                "goal": metadata.get("goal"),
                "confidence": confidence,
                "summary": metadata.get("summary"),
                "action_sequence": actions,
                "selectors": selectors,
            }
        except Exception as ex:
            logger.debug("[BrowserExperienceStore] Retrieval notice: %s", ex)
            return None

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
