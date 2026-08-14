"""
Long-term semantic memory for AuraAI.

Stores durable facts/preferences/topics extracted from past conversations
as embeddings in a local vector store (Chroma), so Aura can recall them in
*future* sessions - "you said last week you're allergic to shellfish."

Important: as of writing, Groq does not serve an embeddings endpoint
(confirmed against console.groq.com/docs/models - it lists chat models,
Whisper, and Orpheus TTS, no embedding model). So embeddings are computed
locally with sentence-transformers:
  - free, no extra network round trip on the voice-latency-critical path
  - Groq is still used for the *extraction* step (turning raw conversation
    into structured facts worth storing)
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Optional

import chromadb
from groq import Groq
from sentence_transformers import SentenceTransformer

EXTRACTION_PROMPT = """Extract any durable facts, preferences, or ongoing \
topics worth remembering long-term from this exchange. Ignore small talk \
and anything purely situational (e.g. "turn the volume up").

Return ONLY a JSON array, no prose, no markdown fences. Each item must look \
like:
{{"fact": "concise standalone statement", "topic": "short topic tag", "importance": 1-5}}

If nothing is worth remembering, return [].

User: {user_text}
Assistant: {assistant_text}"""


class LongTermMemory:
    def __init__(
        self,
        persist_dir: str = "./aura_memory_db",
        collection_name: str = "aura_long_term",
        embed_model: str = "all-MiniLM-L6-v2",
        groq_client: Optional[Groq] = None,
        extractor_model: str = "llama-3.3-70b-versatile",
    ):
        self.embedder = SentenceTransformer(embed_model)
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(collection_name)
        self.groq = groq_client or Groq()
        self.extractor_model = extractor_model

    # ---------------------------------------------------------------- write

    def extract_and_store(self, user_text: str, assistant_text: str) -> list[dict]:
        """
        Ask Groq to pull anything memory-worthy out of a finished exchange.
        Run this off the voice-response critical path (background thread /
        asyncio task) - it shouldn't add latency to what the user hears.
        """
        prompt = EXTRACTION_PROMPT.format(
            user_text=user_text, assistant_text=assistant_text
        )
        resp = self.groq.chat.completions.create(
            model=self.extractor_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        items = self._safe_parse(raw)

        stored = []
        for item in items:
            fact = item.get("fact")
            if not fact:
                continue
            self._store(
                fact,
                topic=item.get("topic", "general"),
                importance=item.get("importance", 3),
            )
            stored.append(item)
        return stored

    @staticmethod
    def _safe_parse(raw: str) -> list[dict]:
        """Groq's json_object mode returns a JSON *object*, not a bare array,
        so the extraction prompt is wrapped defensively - handle both shapes."""
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            # model may wrap the array under a key like "facts" or "items"
            for value in parsed.values():
                if isinstance(value, list):
                    return value
        return []

    def _store(self, fact: str, topic: str, importance: int):
        vec = self.embedder.encode(fact).tolist()
        self.collection.add(
            ids=[str(uuid.uuid4())],
            embeddings=[vec],
            documents=[fact],
            metadatas=[
                {"topic": topic, "importance": importance, "timestamp": time.time()}
            ],
        )

    # ----------------------------------------------------------------- read

    def retrieve(
        self, query: str, k: int = 5, topic: Optional[str] = None
    ) -> list[str]:
        """
        Semantic search over stored facts, re-ranked by a blend of
        similarity, recency, and importance - not similarity alone.
        A 4-month-old low-importance fact shouldn't outrank a fresh
        highly-relevant one just because the wording matches better.
        """
        if self.collection.count() == 0:
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
