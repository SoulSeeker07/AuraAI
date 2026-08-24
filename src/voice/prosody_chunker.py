"""
Prosody-Aware Streaming Text Chunker
Location: src/voice/prosody_chunker.py

Accumulates streaming LLM token chunks and segments them into natural, speakable
prosody units (sentences and clauses) for low-latency Text-to-Speech synthesis.

Invariants & Rules:
1. Sentence Terminators: Flushes immediately on `.`, `!`, `?`, `\n` if it marks a valid sentence end.
2. Short Punchy Sentence Exemption: Complete sentences under 4 words ("Done.", "Sure.", "Firewall is active.")
   are exempt from minimum word count floors and flush immediately without idle delay.
3. Abbreviation & Token Guard: Negative lookbehinds prevent splitting on:
   - Decimal numbers (e.g. 3.14, 0.25)
   - Semantic versions (e.g. v0.29.0, v1.0.0, v2.next)
   - Common abbreviations (e.g. e.g., i.e., etc., vs., Dr., Mr., Mrs., Prof., approx., est., dept.)
   - File paths & extensions (e.g. main.py, audit.json, test.md)
   - URLs / domain names (e.g. aura.ai, github.com)
4. Clause Splitting: Segments on `,`, `;`, `:`, `—` when the buffer exceeds 10 words.
5. Idle-Timeout Flush: Flushes partial clauses if no token arrives for >= 350ms.
"""

import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from .tts_text_cleaner import clean_for_tts

logger = logging.getLogger(__name__)

# Abbreviations that should NOT trigger a sentence split on trailing dot
_ABBREVIATIONS = {
    "e.g", "i.e", "etc", "vs", "dr", "mr", "mrs", "ms", "prof", "approx",
    "est", "dept", "st", "ave", "gen", "rep", "sen", "vol", "no", "fig",
}

# Regex to detect file extensions
_FILE_EXT_RE = re.compile(r"\.(py|json|md|exe|txt|sh|ts|js|html|css|cpp|c|h|rs|go|yaml|yml|toml|ini|csv|log)\b", re.IGNORECASE)

# Regex to detect URLs / domains
_URL_RE = re.compile(r"(https?://\S+|www\.\S+|\b[a-zA-Z0-9_-]+\.(com|org|net|io|ai|dev|gov|edu)\b)", re.IGNORECASE)


class ProsodyAwareChunker:
    """
    Streaming text accumulator and prosody-aware chunker.
    Transforms a token stream into sentence/clause units for real-time TTS.
    """

    def __init__(
        self,
        min_words_for_clause: int = 10,
        max_words_per_chunk: int = 15,
        idle_timeout_seconds: float = 0.35,
        max_buffer_chars: int = 250,
    ):
        self.min_words_for_clause = min_words_for_clause
        self.max_words_per_chunk = max_words_per_chunk
        self.idle_timeout_seconds = idle_timeout_seconds
        self.max_buffer_chars = max_buffer_chars
        self._buffer: str = ""
        self._last_token_time: float = time.time()

    def _is_abbreviation(self, text_before_dot: str) -> bool:
        """Check if the word immediately preceding a dot is a known abbreviation."""
        tokens = text_before_dot.strip().split()
        if not tokens:
            return False
        last_word = tokens[-1].lower().rstrip(".")
        return last_word in _ABBREVIATIONS

    def _is_semver_or_decimal(self, text: str, dot_index: int) -> bool:
        """Check if dot at dot_index is part of a decimal number or semver string."""
        # Check decimal: digit before and digit after
        has_digit_before = dot_index > 0 and text[dot_index - 1].isdigit()
        has_digit_after = dot_index + 1 < len(text) and text[dot_index + 1].isdigit()
        if has_digit_before and has_digit_after:
            return True

        # Check semver prefix: e.g. "v0.29.0", "v1.2", "v2.next"
        prefix = text[:dot_index]
        if re.search(r"\bv\d+$", prefix, re.IGNORECASE):
            return True
        if re.search(r"\bv\d+\.\d+$", prefix, re.IGNORECASE):
            return True

        return False

    def _is_file_or_url(self, text: str, dot_index: int) -> bool:
        """Check if dot at dot_index is part of a file path or URL."""
        # Find token boundary around dot_index
        start = text.rfind(" ", 0, dot_index)
        start = 0 if start == -1 else start + 1
        end = text.find(" ", dot_index)
        end = len(text) if end == -1 else end

        token = text[start:end].rstrip(".,!?")
        if _FILE_EXT_RE.search(token):
            return True
        if _URL_RE.search(token):
            return True
        if "/" in token or "\\" in token:
            return True
        return False

    def _find_split_point(self, text: str, is_final: bool = False) -> int | None:
        """
        Find the character index to split text into a chunk, or None if no split is ready.
        Returns the index *after* the split punctuation (including trailing whitespace).
        """
        if not text:
            return None

        # 1. Check for primary sentence terminators (. ! ? \n)
        for i, char in enumerate(text):
            if char in ("\n", "!", "?"):
                # Always valid sentence boundary
                return i + 1

            if char == ".":
                # Validate that dot is not decimal, semver, abbreviation, or file/URL
                text_before = text[:i]
                if self._is_semver_or_decimal(text, i):
                    continue
                if self._is_abbreviation(text_before):
                    continue
                if self._is_file_or_url(text, i):
                    continue

                # Valid sentence end if followed by space, quote, newline, or is at end (non-digit preceding)
                if i + 1 == len(text):
                    if i > 0 and text[i - 1].isdigit() and not is_final:
                        # Wait for next token to confirm it's not a decimal (e.g. 3.14)
                        continue
                    return i + 1
                elif text[i + 1] in (" ", "\t", "\n", '"', "'", "”", "’"):
                    return i + 1

        # 2. Check for secondary clause delimiters (, ; : — -) if buffer is long
        words = text.strip().split()
        if len(words) >= self.min_words_for_clause or len(text) >= self.max_buffer_chars:
            last_clause_idx = -1
            for i, char in enumerate(text):
                if char in (",", ";", ":", "—") and (i + 1 < len(text) and text[i + 1] in (" ", "\n")):
                    # Ensure clause has at least 4 words before it
                    clause_words = text[:i].strip().split()
                    if len(clause_words) >= 4:
                        last_clause_idx = i + 1

            if last_clause_idx != -1:
                return last_clause_idx

        # 3. Check for hard word-count or buffer ceiling (prevents run-on delimiter-free starvation)
        if len(words) >= self.max_words_per_chunk or len(text) >= self.max_buffer_chars:
            count = 0
            for i, char in enumerate(text):
                if char in (" ", "\t", "\n"):
                    if i > 0 and text[i - 1] not in (" ", "\t", "\n"):
                        count += 1
                        if count >= self.max_words_per_chunk:
                            return i + 1

        # 4. If final stream end, return entire length if anything remains
        if is_final and text.strip():
            return len(text)

        return None

    def feed(self, token: str) -> list[str]:
        """
        Feed a token chunk into the buffer and return any completed prosody chunks.
        """
        if not token:
            return []

        self._buffer += token
        self._last_token_time = time.time()
        chunks: list[str] = []

        while True:
            split_idx = self._find_split_point(self._buffer, is_final=False)
            if split_idx is None:
                break

            chunk_raw = self._buffer[:split_idx]
            self._buffer = self._buffer[split_idx:].lstrip()

            cleaned = clean_for_tts(chunk_raw).strip()
            if cleaned:
                chunks.append(cleaned)

        return chunks

    def flush(self, is_final: bool = True) -> list[str]:
        """
        Flush whatever remains in the buffer.
        """
        if not self._buffer.strip():
            self._buffer = ""
            return []

        chunk_raw = self._buffer
        self._buffer = ""
        cleaned = clean_for_tts(chunk_raw).strip()
        if cleaned:
            return [cleaned]
        return []

    async def stream_chunks(
        self, token_iterator: AsyncIterator[str]
    ) -> AsyncIterator[str]:
        """
        Async generator consuming tokens and yielding prosody chunks in real time
        with idle-timeout flushing.
        """
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        done_event = asyncio.Event()

        async def _consumer():
            try:
                async for token in token_iterator:
                    chunks = self.feed(token)
                    for c in chunks:
                        await queue.put(c)
            except Exception as e:
                logger.error(f"[ProsodyAwareChunker] Token stream error: {e}")
                # On error, append graceful notice if buffer has content
                if self._buffer.strip():
                    await queue.put(clean_for_tts(self._buffer).strip())
                    self._buffer = ""
                await queue.put("I ran into a connection issue, please try again.")
            finally:
                # Flush remaining buffer on normal completion
                for c in self.flush(is_final=True):
                    await queue.put(c)
                done_event.set()
                await queue.put(None)  # Sentinel

        consumer_task = asyncio.create_task(_consumer())

        while True:
            # Wait for next chunk or idle timeout
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=self.idle_timeout_seconds)
                if chunk is None:
                    break
                yield chunk
            except asyncio.TimeoutError:
                # Idle timeout fired: if buffer has text, check if we should flush partial clause
                if not done_event.is_set() and self._buffer.strip():
                    words = self._buffer.strip().split()
                    if len(words) >= 3:
                        # Flush partial clause to maintain voice cadence
                        flushed = self.flush(is_final=False)
                        for c in flushed:
                            yield c

        await consumer_task
