"""
MemoryManager - the "Aura" layer.

Ties short-term (this session) and long-term (across all sessions) memory
together. It acts as the Context Coordinator for Aura's PersonalOSRuntime.

M2 changes:
- Per-turn LLM extraction removed from add_assistant_turn().
  Extraction is now session-level only, triggered at session close.
- _consolidate(transcript) added: formats transcript, calls
  LongTermMemory.extract_candidates(), gates each candidate through
  memory_policy.apply_policy(), calls long_term.store() only on approved facts.
- close_session() added: explicit consolidation trigger (called by
  PersonalOSRuntime on voice loop stop). Idempotent: will not re-extract
  an already-consolidated session.
- add_user_turn() updated to handle new (expired, transcript) tuple from
  ShortTermMemory and trigger automatic consolidation on timeout.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from ai.models import ChatMessage, ChatRequest
from ai.provider_manager import ProviderManager
from core.config import ENABLE_LONG_TERM_MEMORY
from memory.manager.long_term_memory import LongTermMemory
from memory.manager.memory_policy import apply_policy
from memory.manager.short_term_memory import ShortTermMemory, Turn

logger = logging.getLogger(__name__)


class MemoryManager:
    def __init__(
        self,
        provider_manager: ProviderManager,
        summarizer_model: str = "openai/gpt-oss-120b",  # fast JSON summarization
        persist_dir: str = "./aura_memory_db",
        short_term_kwargs: Optional[dict] = None,
    ):
        self.provider_manager = provider_manager
        self.summarizer_model = summarizer_model
        self.short_term = ShortTermMemory(**(short_term_kwargs or {}))

        if ENABLE_LONG_TERM_MEMORY:
            self.long_term = LongTermMemory(
                provider_manager=self.provider_manager,
                persist_dir=persist_dir,
            )
        else:
            self.long_term = None

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
        resp = self.provider_manager.chat(req)
        new_piece = resp.text.strip()
        return f"{self.short_term.rolling_summary} {new_piece}".strip()

    # -------------------------------------------------------------- main API

    def add_user_turn(self, user_text: str) -> None:
        """
        Log a user's utterance.

        Handles two side effects:
        1. Overflow summarization (unchanged from M1).
        2. M2: If the session expired (timeout), trigger background consolidation
           of the expired session's transcript before the buffer was cleared.
        """
        new_session, expired_transcript = self.short_term.add_user_turn(user_text)
        overflow = self.short_term.pop_pending_summary_input()
        if overflow:
            self.short_term.set_rolling_summary(self._summarize_overflow(overflow))

        # M2: consolidate the session that just expired (timeout path)
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

        M2: Per-turn LTM extraction removed. Consolidation is session-level only
        (triggered by timeout or explicit close_session()).
        `user_text` kept in signature for backwards compatibility.
        """
        self.short_term.add_assistant_turn(assistant_text)

    def close_session(self, wait_for_consolidation: bool = False) -> None:
        """
        M2: Explicit session-close trigger (called by PersonalOSRuntime on
        voice loop stop or application shutdown).

        Idempotent: if this session has already been consolidated (e.g. by a
        preceding timeout), this is a no-op to prevent double-extraction.
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


    # --------------------------------------------------------- consolidation

    def _consolidate(self, transcript: list[Turn]) -> None:
        """
        M2: Session-close consolidation pipeline.

        1. Format transcript.
        2. Extract candidates via LongTermMemory (with model fallback chain).
        3. Gate each candidate through memory_policy.apply_policy().
        4. Call long_term.store() only on approved candidates.

        Entirely wrapped in try/except — any failure here is logged and dropped.
        Memory consolidation MUST NEVER break or delay the conversation.
        """
        if not ENABLE_LONG_TERM_MEMORY or not self.long_term:
            return

        if not transcript:
            return

        try:
            transcript_text = "\n".join(
                f"{t.role}: {t.content}" for t in transcript
            )
            logger.info(
                f"[MemoryManager] Consolidating session "
                f"({len(transcript)} turns, {len(transcript_text)} chars)"
            )

            candidates = self.long_term.extract_candidates(transcript_text)
            stored_count = 0
            rejected_count = 0

            for item in candidates:
                verdict = apply_policy(item)
                if verdict.store:
                    self.long_term.store(
                        fact=item["fact"],
                        topic=item.get("topic", "general"),
                        importance=int(item.get("importance", 3)),
                    )
                    stored_count += 1
                else:
                    logger.debug(
                        f"[MemoryManager] Policy rejected: {item.get('fact', '')!r} "
                        f"— {verdict.reason}"
                    )
                    rejected_count += 1

            logger.info(
                f"[MemoryManager] Consolidation complete: "
                f"{stored_count} stored, {rejected_count} rejected by policy"
            )

        except Exception as exc:
            logger.error(
                f"[MemoryManager] Consolidation failed — session not persisted: {exc}",
                exc_info=True,
            )
            # Do NOT re-raise. Consolidation failure must never propagate.

    # ----------------------------------------------------------- context API

    def get_raw_turns(self) -> list[Turn]:
        """Get the raw turns, primarily for ReferenceResolver to resolve pronouns."""
        return self.short_term.get_raw_turns()

    def get_context_messages(self, query: str | None = None) -> list[dict]:
        """
        Build the context messages for LLM execution.
        Note: The caller is responsible for prepending the Aura System Persona.
        """
        messages = []

        # Inject long-term semantic memory if enabled and a query is provided
        if ENABLE_LONG_TERM_MEMORY and self.long_term and query:
            memories = self.long_term.retrieve(query, k=5)
            if memories:
                memory_block = "Relevant memories:\n" + "\n".join(
                    f"- {m}" for m in memories
                )
                messages.append({"role": "system", "content": memory_block})

        # Append the short-term context (rolling summary + recent turns)
        messages.extend(self.short_term.get_context_messages())

        return messages
