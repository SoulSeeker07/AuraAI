"""
MemoryManager - the "Aura" Context Coordinator layer.

Ties short-term working memory (this session) and unified persistent long-term
memory (SQLite VectorMemoryEngine + CognitiveMemoryEngine) together.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from typing import Any, Optional

from ai.models import ChatMessage, ChatRequest
from ai.provider_manager import ProviderManager
from core.config import ENABLE_LONG_TERM_MEMORY
from memory.manager.memory_policy import apply_policy
from memory.manager.short_term_memory import ShortTermMemory, Turn

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
Analyze this conversation transcript and extract any enduring facts about the user,
their preferences, their projects, or persistent instructions they gave.

Rules:
- Output ONLY valid JSON — a list of objects. No preamble, no markdown fences.
- Format: [{"fact": "...", "topic": "...", "importance": 1-5}]
- Importance scale:
    5 = Critical identity / core workflow preference
    4 = Important project detail / strong preference
    3 = Useful context / tool preference
    2 = Minor detail
    1 = Ephemeral
- If no enduring facts are present, return an empty list: []
- NEVER extract transient questions, one-off commands, or conversational filler.

Transcript:
{transcript_text}
"""


class MemoryManager:
    def __init__(
        self,
        provider_manager: ProviderManager,
        summarizer_model: str = "openai/gpt-oss-120b",  # fast JSON summarization
        persist_dir: str = "./aura_memory_db",
        short_term_kwargs: Optional[dict] = None,
        memory: Optional[Any] = None,
    ):
        self.provider_manager = provider_manager
        self.summarizer_model = summarizer_model
        self._persist_dir = persist_dir
        self.short_term = ShortTermMemory(**(short_term_kwargs or {}))
        self.memory = memory
        self._long_term = None
        self._long_term_initialized = False

    @property
    def long_term(self):
        """Legacy ChromaDB accessor — kept only for backwards compatibility when explicitly enabled."""
        if not self._long_term_initialized:
            self._long_term_initialized = True
            if ENABLE_LONG_TERM_MEMORY:
                try:
                    from memory.manager.long_term_memory import LongTermMemory
                    self._long_term = LongTermMemory(
                        provider_manager=self.provider_manager,
                        persist_dir=self._persist_dir,
                    )
                except Exception as e:
                    logger.warning("[MemoryManager] LongTermMemory lazy load notice: %s", e)
                    self._long_term = None
            else:
                self._long_term = None
        return self._long_term

    @long_term.setter
    def long_term(self, val):
        self._long_term = val
        self._long_term_initialized = True

    # ---------------------------------------------------------- summarizing

    def _summarize_overflow(self, overflow_turns: list[Turn]) -> str:
        if not overflow_turns:
            return self.short_term.rolling_summary

        text = "\n".join(f"{t.role}: {t.content}" for t in overflow_turns)
        prompt = (
            "Summarize this part of a conversation in 2-3 sentences. Keep "
            "any concrete facts, numbers, or decisions - drop small talk:"
            f"\n\n{text}"
        )

        req = ChatRequest(
            messages=[ChatMessage(role="user", content=prompt)],
            model=self.summarizer_model,
            temperature=0.0,
        )
        try:
            resp = self.provider_manager.chat(req)
            return resp.text.strip()
        except Exception as e:
            logger.warning("[MemoryManager] Overflow summarization failed: %s", e)
            return self.short_term.rolling_summary

    # -------------------------------------------------------------- main API

    def add_user_turn(self, user_text: str) -> None:
        """
        Log a user's utterance.
        """
        new_session, expired_transcript = self.short_term.add_user_turn(user_text)
        overflow = self.short_term.pop_pending_summary_input()
        if overflow:
            self.short_term.set_rolling_summary(self._summarize_overflow(overflow))

        # Consolidate session on timeout
        if new_session and expired_transcript:
            threading.Thread(
                target=self._consolidate,
                args=(expired_transcript,),
                daemon=True,
                name="aura-memory-consolidate-timeout",
            ).start()

    def add_assistant_turn(self, assistant_text: str, user_text: str | None = None) -> None:
        """
        Log the assistant's reply.
        """
        self.short_term.add_assistant_turn(assistant_text)

    def close_session(self, wait_for_consolidation: bool = False) -> None:
        """
        Explicit session-close trigger on shutdown or voice loop stop.
        """
        if self.short_term.session_consolidated:
            logger.info(
                f"[MemoryManager] close_session() called but session "
                f"{self.short_term.session_id!r} already consolidated — skipping."
            )
            return

        transcript = self.short_term.pop_session_transcript()
        if not transcript:
            logger.info("[MemoryManager] close_session() called on empty session — nothing to consolidate.")
            return

        self.short_term.session_consolidated = True
        
        if wait_for_consolidation:
            logger.info("[MemoryManager] Running synchronous consolidation (shutdown).")
            self._consolidate(transcript)
        else:
            threading.Thread(
                target=self._consolidate,
                args=(transcript,),
                daemon=True,
                name="aura-memory-consolidate-explicit",
            ).start()

    # --------------------------------------------------------- candidate extraction

    def _extract_candidates(self, transcript_text: str) -> list[dict]:
        """Extract memory-worthy candidates from session transcript using LLM."""
        prompt = EXTRACTION_PROMPT.format(transcript_text=transcript_text)
        models = [self.summarizer_model, "llama-3.3-70b-versatile"]

        for model in models:
            try:
                req = ChatRequest(
                    messages=[ChatMessage(role="user", content=prompt)],
                    model=model,
                    temperature=0.0,
                )
                resp = self.provider_manager.chat(req)
                raw = resp.text.strip()
                if raw.startswith("```json"):
                    raw = raw[7:]
                if raw.startswith("```"):
                    raw = raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                data = json.loads(raw.strip())
                if isinstance(data, list):
                    logger.info(f"[MemoryManager] Extracted {len(data)} candidate(s) using {model}")
                    return data
            except Exception as exc:
                logger.warning(f"[MemoryManager] Candidate extraction note ({model}): {exc}")

        return []

    # --------------------------------------------------------- consolidation

    def _consolidate(self, transcript: list[Turn]) -> None:
        """
        Session-close consolidation pipeline:
        1. Format transcript.
        2. Extract candidates via LLM.
        3. Gate each candidate through policy.
        4. Upsert approved candidates directly into Memory.db (facts + embeddings + cognitive).
        """
        if not transcript:
            return

        try:
            transcript_text = "\n".join(f"{t.role}: {t.content}" for t in transcript)
            logger.info(
                f"[MemoryManager] Consolidating session ({len(transcript)} turns, {len(transcript_text)} chars)"
            )

            candidates = self._extract_candidates(transcript_text)
            stored_count = 0
            rejected_count = 0

            for item in candidates:
                if not isinstance(item, dict) or not item.get("fact"):
                    continue
                verdict = apply_policy(item)
                if verdict.store:
                    fact_text = item["fact"]
                    topic = item.get("topic", "profile")
                    
                    if self.memory:
                        clean_key = re.sub(r'[^a-zA-Z0-9_]', '_', fact_text[:30]).strip('_').lower()
                        self.memory.upsert_fact(category=topic, key=clean_key or "fact", value=fact_text)
                        stored_count += 1
                    elif ENABLE_LONG_TERM_MEMORY and self.long_term:
                        self.long_term.store(
                            fact=fact_text,
                            topic=topic,
                            importance=int(item.get("importance", 3)),
                        )
                        stored_count += 1
                else:
                    logger.debug(
                        f"[MemoryManager] Policy rejected: {item.get('fact', '')!r} — {verdict.reason}"
                    )
                    rejected_count += 1

            logger.info(
                f"[MemoryManager] Consolidation complete: {stored_count} stored, {rejected_count} rejected by policy"
            )

        except Exception as exc:
            logger.error(f"[MemoryManager] Consolidation failed: {exc}", exc_info=True)

    # ----------------------------------------------------------- context API

    def get_raw_turns(self) -> list[Turn]:
        """Get raw turns for reference resolution."""
        return self.short_term.get_raw_turns()

    def get_context_messages(self, query: str | None = None) -> list[dict]:
        """
        Build context messages:
        1. Query unified SQLite VectorMemoryEngine via self.memory.
        2. Append short-term conversational sliding window.
        """
        messages = []

        # Unified Vector Semantic Recall
        if self.memory and query:
            try:
                rel_facts = self.memory.get_relevant_facts(query, limit=5)
                if rel_facts:
                    memory_block = "Relevant memories:\n" + "\n".join(
                        f"- {f.value if hasattr(f, 'value') else f}" for f in rel_facts
                    )
                    messages.append({"role": "system", "content": memory_block})
            except Exception as e:
                logger.debug(f"[MemoryManager] Semantic recall note: {e}")

        # Legacy ChromaDB fallback if enabled
        elif ENABLE_LONG_TERM_MEMORY and self.long_term and query:
            memories = self.long_term.retrieve(query, k=5)
            if memories:
                memory_block = "Relevant memories:\n" + "\n".join(f"- {m}" for m in memories)
                messages.append({"role": "system", "content": memory_block})

        # Append short-term context (rolling summary + recent turns)
        messages.extend(self.short_term.get_context_messages())

        return messages
