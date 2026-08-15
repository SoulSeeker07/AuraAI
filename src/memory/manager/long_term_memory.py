"""
Long-term semantic memory for AuraAI — M2 revision.

Stores durable facts/preferences/topics extracted from past conversations
as embeddings in a local vector store (Chroma), so Aura can recall them in
*future* sessions.

M2 changes:
- extract_and_store() → extract_candidates(): accepts a full session transcript
  (not a single exchange) so cross-turn patterns are visible to the extractor.
- Model fallback chain: openai/gpt-oss-120b → llama-3.3-70b-versatile →
  llama-3.1-8b-instant → empty list (never raises, never breaks conversation).
- _store() publicized as store() — called by MemoryManager._consolidate() only
  after memory_policy.apply_policy() approves the candidate.
- LLM is a candidate producer only; it has no authority over Chroma writes.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Optional

import chromadb
from sentence_transformers import SentenceTransformer

from ai.models import ChatMessage, ChatRequest
from ai.provider_manager import ProviderManager
from core.config import MEMORY_EXTRACTION_MODELS

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
You are a memory extraction assistant. Given a conversation transcript, identify \
any facts, preferences, or ongoing topics that are worth remembering across sessions.

Rules:
- Extract ONLY durable, user-specific facts (preferences, habits, stated goals, \
  recurring topics).
- IGNORE one-off commands, tool results, calculations, and anything purely situational.
- IGNORE anything that contains credentials, passwords, card numbers, PINs, or tokens.
- Return ONLY a raw JSON array. Do not use markdown code blocks or fences.
- Each item must look like:
  {{"fact": "concise standalone statement", "topic": "short topic tag", "importance": 1-5}}
- If nothing is worth remembering, return [].

Conversation transcript:
{transcript_text}"""


class LongTermMemory:
    def __init__(
        self,
        provider_manager: ProviderManager,
        persist_dir: str = "./aura_memory_db",
        collection_name: str = "aura_long_term",
        embed_model: str = "all-MiniLM-L6-v2",
    ):
        try:
            self.embedder = SentenceTransformer(embed_model, local_files_only=True)
        except Exception as e:
            logger.warning(
                f"[LongTermMemory] Local embedding model '{embed_model}' not found in cache or offline: {e}. "
                "Disabling semantic embedding recall gracefully to eliminate network lookup freezes during turns."
            )
            self.embedder = None
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(collection_name)
        self.provider_manager = provider_manager
        # Fallback chain from config — do NOT override here
        self._extraction_models = MEMORY_EXTRACTION_MODELS

    # ---------------------------------------------------------------- write

    def extract_candidates(self, transcript_text: str) -> list[dict]:
        """
        Ask the LLM to identify memory-worthy candidates from a full session
        transcript. Returns a list of candidate dicts:
            [{"fact": ..., "topic": ..., "importance": ...}]

        Tries each model in MEMORY_EXTRACTION_MODELS in order. On all failures,
        returns [] — never raises. The caller (MemoryManager._consolidate) applies
        the policy gate and calls store() on approved candidates.
        """
        prompt = EXTRACTION_PROMPT.format(transcript_text=transcript_text)

        for model in self._extraction_models:
            try:
                req = ChatRequest(
                    messages=[ChatMessage(role="user", content=prompt)],
                    model=model,
                    temperature=0.0,
                )
                resp = self.provider_manager.chat(req)
                raw = resp.text.strip()
                candidates = self._safe_parse(raw)
                if candidates is not None:
                    logger.info(
                        f"[LTM] Extracted {len(candidates)} candidate(s) using {model}"
                    )
                    return candidates
            except Exception as exc:
                logger.warning(f"[LTM] Extraction failed with model {model!r}: {exc}")

        logger.warning("[LTM] All extraction models failed — no candidates produced")
        return []

    def store(self, fact: str, topic: str, importance: int) -> None:
        """
        Persist a policy-approved fact to Chroma.
        Called only by MemoryManager._consolidate() after apply_policy() approves.
        """
        if not self.embedder:
            logger.debug("[LTM] Skipping semantic store (embedder unavailable)")
            return

        vec = self.embedder.encode(fact).tolist()
        self.collection.add(
            ids=[str(uuid.uuid4())],
            embeddings=[vec],
            documents=[fact],
            metadatas=[
                {"topic": topic, "importance": importance, "timestamp": time.time()}
            ],
        )
        logger.info(f"[LTM] Stored: {fact!r} (topic={topic}, importance={importance})")

    # ----------------------------------------------------------------- read

    def retrieve(
        self, query: str, k: int = 5, topic: Optional[str] = None
    ) -> list[str]:
        """
        Semantic search over stored facts, re-ranked by a blend of
        similarity, recency, and importance.
        """
        if not self.embedder or self.collection.count() == 0:
            return []

        vec = self.embedder.encode(query).tolist()
        where = {"topic": topic} if topic else None
        results = self.collection.query(
            query_embeddings=[vec],
            n_results=min(k * 3, self.collection.count()),  # over-fetch, re-rank, trim
            where=where,
        )
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        now = time.time()
        scored = []
        for doc, meta, dist in zip(docs, metas, dists):
            age_days = (now - meta.get("timestamp", now)) / 86400
            recency_score = 1 / (1 + age_days / 30)  # ~halves relevance every month
            importance_score = meta.get("importance", 3) / 5
            similarity = 1 - dist  # chroma returns cosine distance by default
            score = 0.6 * similarity + 0.25 * recency_score + 0.15 * importance_score
            scored.append((score, doc))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [doc for _, doc in scored[:k]]

    # ----------------------------------------------------------- parsing

    @staticmethod
    def _safe_parse(raw: str) -> list[dict] | None:
        """
        Defensively parse JSON. Returns None if completely unparseable
        (signals caller to try next model), returns [] for valid empty results.
        """
        raw = raw.strip()
        # Strip markdown fences defensively (prompt asks not to use them)
        if raw.startswith("```json"):
            raw = raw[7:]
        elif raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None  # signal: try next model

        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            # model may wrap the array under a key like "facts" or "items"
            for value in parsed.values():
                if isinstance(value, list):
                    return value
        return []
