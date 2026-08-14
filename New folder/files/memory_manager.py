"""
MemoryManager - the "Aura" layer.

Ties short-term (this session) and long-term (across all sessions) memory
together and builds the exact message list sent to Groq for each turn:
it decides what context the LLM actually sees, which is what keeps
answers on-topic and lets Aura reference things you told it before.
"""

from __future__ import annotations

import threading
from typing import Optional

from groq import Groq

from long_term_memory import LongTermMemory
from short_term_memory import ShortTermMemory

SYSTEM_PROMPT = (
    "You are Aura, a voice assistant. Keep replies concise - this is "
    "spoken aloud, not read. Use the 'Relevant memories' block only when "
    "it actually helps answer the current question; don't force it in "
    "when it's not needed."
)


class MemoryManager:
    def __init__(
        self,
        groq_client: Optional[Groq] = None,
        chat_model: str = "llama-3.3-70b-versatile",
        summarizer_model: str = "llama-3.1-8b-instant",  # cheap/fast, just condensing
        persist_dir: str = "./aura_memory_db",
        short_term_kwargs: Optional[dict] = None,
    ):
        self.groq = groq_client or Groq()
        self.chat_model = chat_model
        self.summarizer_model = summarizer_model
        self.short_term = ShortTermMemory(**(short_term_kwargs or {}))
        self.long_term = LongTermMemory(persist_dir=persist_dir, groq_client=self.groq)

    # ---------------------------------------------------------- summarizing

    def _summarize_overflow(self, overflow_turns) -> str:
        if not overflow_turns:
            return self.short_term.rolling_summary

        text = "\n".join(f"{t.role}: {t.content}" for t in overflow_turns)
        prompt = (
            "Summarize this part of a conversation in 2-3 sentences. Keep "
            "any concrete facts, numbers, or decisions - drop small talk:"
            f"\n\n{text}"
        )
        resp = self.groq.chat.completions.create(
            model=self.summarizer_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        new_piece = resp.choices[0].message.content.strip()
        return f"{self.short_term.rolling_summary} {new_piece}".strip()

    # -------------------------------------------------------------- main API

    def handle_user_turn(self, user_text: str) -> str:
        """Run one full turn: update short-term memory, pull relevant
        long-term memories, call the LLM, store the reply, and kick off
        async fact extraction. Returns the text to speak back."""

        self.short_term.add_turn("user", user_text)
        overflow = self.short_term.pop_pending_summary_input()
        if overflow:
            self.short_term.set_rolling_summary(self._summarize_overflow(overflow))

        memories = self.long_term.retrieve(user_text, k=5)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if memories:
            memory_block = "Relevant memories:\n" + "\n".join(
                f"- {m}" for m in memories
            )
            messages.append({"role": "system", "content": memory_block})
        messages.extend(self.short_term.get_context_messages())

        resp = self.groq.chat.completions.create(
            model=self.chat_model,
            messages=messages,
            temperature=0.6,
        )
        assistant_text = resp.choices[0].message.content
        self.short_term.add_turn("assistant", assistant_text)

        # Fact extraction hits the LLM again - never make the user wait on
        # it. Fire it in a background thread so handle_user_turn returns as
        # soon as there's something to speak.
        threading.Thread(
            target=self.long_term.extract_and_store,
            args=(user_text, assistant_text),
            daemon=True,
        ).start()

        return assistant_text
