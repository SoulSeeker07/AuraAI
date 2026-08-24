"""
Unit Tests: Streaming Low-Latency Voice Pipeline
Location: tests/unit/test_streaming_voice_pipeline.py
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from voice.prosody_chunker import ProsodyAwareChunker
from voice.tts_manager import ChunkedStreamPlayer, OrderedStreamSynthesizer


# ── ProsodyAwareChunker Tests ───────────────────────────────────────────────

def test_prosody_chunker_sentence_boundaries():
    """Verify standard sentence boundary splitting on '.', '!', '?'."""
    chunker = ProsodyAwareChunker()
    tokens = ["Hello ", "there! ", "How ", "are ", "you ", "doing? ", "I am ", "ready."]
    all_chunks = []
    for t in tokens:
        all_chunks.extend(chunker.feed(t))
    all_chunks.extend(chunker.flush())

    assert len(all_chunks) == 3
    assert all_chunks[0] == "Hello there!"
    assert all_chunks[1] == "How are you doing?"
    assert all_chunks[2] == "I am ready."


def test_prosody_chunker_semver_and_decimals():
    """Verify semantic versions (v0.29.0) and decimal numbers (3.14) are NOT split."""
    chunker = ProsodyAwareChunker()
    text = "Upgraded to v0.29.0 today with 3.14 seconds latency. All systems green."
    chunks = []
    for word in text.split(" "):
        chunks.extend(chunker.feed(word + " "))
    chunks.extend(chunker.flush())

    assert len(chunks) == 2
    assert chunks[0] == "Upgraded to v0.29.0 today with 3.14 seconds latency."
    assert chunks[1] == "All systems green."


def test_prosody_chunker_abbreviations_and_files():
    """Verify common abbreviations (e.g., i.e., Dr.) and file extensions (main.py) are NOT split."""
    chunker = ProsodyAwareChunker()
    text = "Please check main.py, e.g. run pytest first. Dr. Smith approved it."
    chunks = []
    for word in text.split(" "):
        chunks.extend(chunker.feed(word + " "))
    chunks.extend(chunker.flush())

    assert len(chunks) == 2
    assert "main.py, e.g. run pytest first." in chunks[0]
    assert "Dr. Smith approved it." in chunks[1]


def test_prosody_chunker_short_punchy_exemption():
    """Verify short punchy confirmations (<= 3 words ending in '.') flush immediately."""
    chunker = ProsodyAwareChunker()
    
    # "Done." should flush immediately on feed
    chunks1 = chunker.feed("Done. ")
    assert chunks1 == ["Done."]

    # "Sure." should flush immediately
    chunks2 = chunker.feed("Sure! ")
    assert chunks2 == ["Sure!"]

    # "Firewall is active." should flush immediately
    chunks3 = chunker.feed("Firewall is active. ")
    assert chunks3 == ["Firewall is active."]


def test_prosody_chunker_clause_splitting():
    """Verify long sentences (>= 10 words) are segmented on clause boundaries."""
    chunker = ProsodyAwareChunker(min_words_for_clause=8)
    long_sentence = (
        "I have audited all network interfaces and verified firewall telemetry, "
        "and now I am compiling the executive security compliance report."
    )
    chunks = []
    for word in long_sentence.split(" "):
        chunks.extend(chunker.feed(word + " "))
    chunks.extend(chunker.flush())

    assert len(chunks) == 2
    assert chunks[0].endswith(",")
    assert "compiling the executive security compliance report" in chunks[1]


@pytest.mark.asyncio
async def test_prosody_chunker_async_streaming_and_idle_timeout():
    """Verify async streaming generator with idle timeout flush."""
    chunker = ProsodyAwareChunker(idle_timeout_seconds=0.1)

    async def _token_source():
        yield "Starting "
        yield "background "
        yield "task "
        # Pause longer than idle timeout
        await asyncio.sleep(0.15)
        yield "and continuing "
        yield "now."

    received = []
    async for chunk in chunker.stream_chunks(_token_source()):
        received.append(chunk)

    assert len(received) >= 2
    assert "Starting background task" in received[0]
    assert "continuing now." in received[1]


# ── OrderedStreamSynthesizer Tests ──────────────────────────────────────────

def test_ordered_synthesizer_strict_fifo_playback():
    """
    Verify strict FIFO playback ordering under variable synthesis latencies.
    Chunk 2 finishes in 10ms, Chunk 1 finishes in 60ms.
    Playback MUST receive Chunk 1 first, then Chunk 2.
    """
    mock_player = MagicMock(spec=ChunkedStreamPlayer)
    fed_audio = []
    mock_player.feed.side_effect = lambda data: fed_audio.append(data)
    mock_player.start_utterance.return_value = True

    def _variable_latency_synthesize(text: str) -> bytes:
        if "First" in text:
            time.sleep(0.06)  # Slow
            return b"AUDIO_CHUNK_1"
        else:
            time.sleep(0.01)  # Fast
            return b"AUDIO_CHUNK_2"

    synthesizer = OrderedStreamSynthesizer(
        synthesize_fn=_variable_latency_synthesize,
        player=mock_player,
        max_workers=2,
    )

    gen_id = 1
    assert synthesizer.start(gen_id) is True

    # Submit Chunk 1 (slow) and Chunk 2 (fast)
    synthesizer.submit_chunk("First long chunk", gen_id)
    synthesizer.submit_chunk("Second fast chunk", gen_id)
    synthesizer.finish_submitting(gen_id)

    # Wait for playback thread to complete
    synthesizer._playback_thread.join(timeout=2.0)

    # Assert strict FIFO audio output
    assert fed_audio == [b"AUDIO_CHUNK_1", b"AUDIO_CHUNK_2"]
    mock_player.finish.assert_called_once()


def test_barge_in_generation_epoch_invalidation():
    """Verify that incrementing generation epoch cancels pending chunks and aborts player."""
    mock_player = MagicMock(spec=ChunkedStreamPlayer)
    fed_audio = []
    mock_player.feed.side_effect = lambda data: fed_audio.append(data)
    mock_player.start_utterance.return_value = True

    def _synthesize(text: str) -> bytes:
        time.sleep(0.05)
        return text.encode("utf-8")

    synthesizer = OrderedStreamSynthesizer(
        synthesize_fn=_synthesize,
        player=mock_player,
        max_workers=2,
    )

    gen_id_1 = 1
    synthesizer.start(gen_id_1)
    synthesizer.submit_chunk("Chunk from turn 1", gen_id_1)

    # Interrupt / Start new turn with gen_id_2 immediately
    gen_id_2 = 2
    synthesizer.start(gen_id_2)
    synthesizer.submit_chunk("Chunk from turn 2", gen_id_2)
    synthesizer.finish_submitting(gen_id_2)

    synthesizer._playback_thread.join(timeout=2.0)

    # Turn 1 chunk must NOT have been fed to player
    assert b"Chunk from turn 1" not in fed_audio
    assert b"Chunk from turn 2" in fed_audio


# ── AuraCore Streaming Contract Tests ───────────────────────────────────────

@pytest.mark.asyncio
async def test_auracore_process_request_stream_chat():
    """Verify AuraCore.process_request_stream yields streamed tokens for chat."""
    from core.aura_core import AuraCore

    aura = AuraCore()
    aura.llm_enabled = True
    mock_groq = MagicMock()
    mock_chunk1 = MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello "))])
    mock_chunk2 = MagicMock(choices=[MagicMock(delta=MagicMock(content="there!"))])
    mock_groq.chat.completions.create.return_value = [mock_chunk1, mock_chunk2]
    aura.groq_client = mock_groq

    tokens = []
    async for t in aura.process_request_stream("Hello"):
        tokens.append(t)

    assert "".join(tokens) == "Hello there!"


@pytest.mark.asyncio
async def test_auracore_confirmation_gate_hard_blocks_stream():
    """Verify that when confirmation is pending, process_request_stream yields confirmation prompt and stops."""
    from core.aura_core import AuraCore
    from core.orchestration.confirmation import ActionPlanConfirmation
    from core.orchestration.master_orchestrator import MasterOrchestrator
    from core.planning.action_plan import ActionPlan

    aura = AuraCore()
    orchestrator = MasterOrchestrator.get_instance()

    # Real ActionPlanConfirmation, not a MagicMock: a mock auto-creates whatever
    # attribute the caller reads, so it cannot catch a wrong field name. This
    # test previously set `mock_conf.plan.goal` and passed while the production
    # code raised AttributeError against the real dataclass field `action_plan`.
    mock_conf = ActionPlanConfirmation(
        session_id="test-session",
        action_plan=ActionPlan(
            action="delete_file",
            target="audit.log",
            goal="delete audit logs",
            capability="delete_file",
        ),
        prompt="Confirm deletion of audit logs?",
    )
    orchestrator.check_pending_confirmation = MagicMock(return_value=mock_conf)

    with patch.object(orchestrator, "process_request_async") as mock_exec:
        mock_result = MagicMock(observations=["Action requires user confirmation."])
        mock_exec.return_value = mock_result

        chunks = []
        async for c in aura.process_request_stream("Delete all audit logs"):
            chunks.append(c)

        # Must yield confirmation prompt
        assert any("I need your confirmation to delete audit logs" in c for c in chunks)


def test_prosody_chunker_hard_word_ceiling_on_run_on_sentence():
    """Verify that a continuous stream of 25+ words with NO punctuation is bounded by max_words_per_chunk."""
    chunker = ProsodyAwareChunker(max_words_per_chunk=12)

    # 25 words with zero punctuation delimiters
    run_on_words = [
        "this", "is", "a", "very", "long", "continuous", "stream", "of", "words", "without",
        "any", "punctuation", "delimiters", "whatsoever", "designed", "to", "test", "if",
        "the", "chunker", "flushes", "at", "the", "word", "ceiling"
    ]

    all_chunks = []
    for w in run_on_words:
        all_chunks.extend(chunker.feed(w + " "))
    all_chunks.extend(chunker.flush())

    # Must be split into at least 2 bounded chunks (not 1 giant delayed chunk)
    assert len(all_chunks) >= 2
    # First chunk should have at most 12 words
    assert len(all_chunks[0].split()) <= 12
    assert "this is a very long continuous stream of words without any punctuation" in all_chunks[0]


@pytest.mark.asyncio
async def test_auracore_tool_execution_yields_contextual_filler_utterance():
    """Verify that multi-step/tool execution emits immediate contextual acoustic filler."""
    from core.aura_core import AuraCore
    from core.orchestration.master_orchestrator import MasterOrchestrator

    aura = AuraCore()
    orchestrator = MasterOrchestrator.get_instance()
    orchestrator.check_pending_confirmation = MagicMock(return_value=None)

    # 1. Research / Web Search query
    with patch.object(orchestrator, "process_request_async") as mock_exec:
        mock_result = MagicMock(observations=["Found 3 Python tutorials on YouTube."], data={"decision": {"intent_type": "research"}}, final_output="Found 3 tutorials.")
        mock_exec.return_value = mock_result

        chunks = []
        async for c in aura.process_request_stream("Search YouTube for Python tutorials"):
            chunks.append(c)

        # First chunk must be the contextual filler
        assert chunks[0] == "Looking that up now... "
        assert any("Found" in c for c in chunks)

    # 2. When yield_filler=False, no filler is emitted
    with patch.object(orchestrator, "process_request_async") as mock_exec:
        mock_result = MagicMock(observations=["Found 3 Python tutorials."], data={"decision": {"intent_type": "research"}}, final_output="Found 3 tutorials.")
        mock_exec.return_value = mock_result

        chunks = []
        async for c in aura.process_request_stream("Search YouTube for Python tutorials", yield_filler=False):
            chunks.append(c)

        assert chunks[0] != "Looking that up now... "


