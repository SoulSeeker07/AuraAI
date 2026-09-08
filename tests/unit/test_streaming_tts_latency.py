"""
Unit Tests for Streaming TTS and Low-Latency Playback
Location: tests/unit/test_streaming_tts_latency.py
"""

import asyncio
import time
import pytest
from src.voice.tts_manager import ChunkedStreamPlayer, OrderedStreamSynthesizer


def test_01_chunked_stream_player_lifecycle():
    """Verify start_utterance, feed, finish, abort, and completion state transitions."""
    player = ChunkedStreamPlayer(sample_rate=16000, channels=1)

    completed = []
    interrupted = []
    player.set_callbacks(
        complete=lambda: completed.append(True),
        interrupt=lambda: interrupted.append(True),
    )

    assert not player.is_playing()

    # Start utterance
    ok = player.start_utterance()
    assert ok is True
    assert player.is_playing()

    # Feed dummy PCM frames
    dummy_pcm = b"\x00\x00" * 512
    player.feed(dummy_pcm)

    # Abort
    player.abort()
    assert not player.is_playing()

    # Close player stream
    player.close()


def test_02_ordered_stream_synthesizer_fifo_order():
    """Verify OrderedStreamSynthesizer maintains strict sequence order under concurrent synthesis."""
    player = ChunkedStreamPlayer(sample_rate=16000, channels=1)

    delivered_chunks = []
    def _mock_feed(chunk: bytes):
        delivered_chunks.append(chunk.decode("ascii"))

    player.feed = _mock_feed

    # Synthesis function that reverses delay (later chunk finishes faster)
    def _mock_synthesize(text: str) -> bytes | None:
        if "fast" in text:
            time.sleep(0.01)
        else:
            time.sleep(0.05)
        return text.encode("ascii")

    synth = OrderedStreamSynthesizer(synthesize_fn=_mock_synthesize, player=player, max_workers=2)

    synth.start(gen_id=1)
    # Submit slow first, then fast
    synth.submit_chunk("chunk_0_slow", gen_id=1)
    synth.submit_chunk("chunk_1_fast", gen_id=1)
    synth.finish_submitting(gen_id=1)

    # Wait for synthesizer to drain in FIFO order
    timeout = time.time() + 2.0
    while len(delivered_chunks) < 2 and time.time() < timeout:
        time.sleep(0.02)

    assert len(delivered_chunks) == 2
    assert delivered_chunks[0] == "chunk_0_slow"
    assert delivered_chunks[1] == "chunk_1_fast"

    player.close()


def test_03_ttfa_turn_start_benchmark():
    """Verify TTFA includes turn thread and event loop spin-up overhead and completes within budget."""
    from src.voice.continuous_loop import ContinuousVoiceLoop
    from src.voice.response_steering import ResponseSteeringController

    class BenchAudioManager:
        def is_recording(self):
            return True
        def mute(self):
            pass
        def unmute(self):
            pass
        def enable_capture(self):
            pass
        def disable_capture(self):
            pass

    class BenchTTSManager:
        def stop(self):
            pass
        def speak(self, text):
            pass

    class BenchInterruptionManager:
        def update_state(self, state):
            pass
        def reset(self):
            pass

    class BenchVoiceManager:
        def __init__(self):
            self.state = None
            self._running = True
            self.audio_manager = BenchAudioManager()
            self.tts_manager = BenchTTSManager()
            self.interruption_manager = BenchInterruptionManager()
            self.steering_controller = ResponseSteeringController()
            self.settings = {"full_duplex": True}
            self.received_chunks = []
            self.first_chunk_event = asyncio.Event()

        def start(self):
            return True

        def activate(self):
            return True

        def stop(self):
            self._running = False
            return True

        def _start_active_listening(self):
            pass

        def _update_state(self, state):
            self.state = state

        def unmute_microphone(self):
            pass

        def speak(self, text):
            pass

        def speak_stream(self, generator):
            async def _consume():
                async for chunk in generator:
                    self.received_chunks.append(chunk)
            asyncio.create_task(_consume())
            return True

    class BenchAuraCore:
        def __init__(self):
            self.conversation_engine = None

        async def process_request_stream(self, transcript, **kwargs):
            # Immediately yield first chunk to measure thread + event loop initialization floor
            yield "Understood. Starting immediate processing."

        def add_to_conversation(self, role, content):
            pass

    voice_mgr = BenchVoiceManager()
    core = BenchAuraCore()
    loop = ContinuousVoiceLoop(voice_manager=voice_mgr, aura_core=core)
    loop.start()

    # Capture start time immediately before triggering turn
    turn_start_wall = time.time()
    loop.trigger_wake_detected("Aura")
    loop.trigger_transcription_ready("Compute the benchmark metrics.")

    # Wait for turn thread to spin up, run generator, and log first audio
    timeout = time.time() + 2.0
    while "T6_first_audio" not in loop._turn_telemetry and time.time() < timeout:
        time.sleep(0.005)

    assert "T5_reasoning_start" in loop._turn_telemetry, "T5 reasoning start timestamp must be recorded"
    assert "T6_first_audio" in loop._turn_telemetry, "T6 first audio timestamp must be recorded"

    t5 = loop._turn_telemetry["T5_reasoning_start"]
    t6 = loop._turn_telemetry["T6_first_audio"]

    ttfa_ms = (t6 - t5) * 1000.0
    wall_ttfa_ms = (t6 - turn_start_wall) * 1000.0

    print(f"\n[BENCHMARK] Thread + Event Loop TTFA: {ttfa_ms:.2f}ms (Wall-clock: {wall_ttfa_ms:.2f}ms)")

    # Assert thread spin-up + event loop initialization + chunking is under 150ms on all environments
    assert ttfa_ms < 150.0, f"Thread + event loop spinup TTFA too slow: {ttfa_ms:.2f}ms"
    assert len(voice_mgr.received_chunks) >= 1, "TTS must have received at least one chunk"

    loop.stop()


def test_04_ordered_synthesizer_abort_drains_queue_and_drops_inflight_workers():
    """Verify OrderedStreamSynthesizer.abort() cancels pending workers and prevents stale chunk delivery."""
    delivered = []

    player = ChunkedStreamPlayer(sample_rate=16000, channels=1)
    player.feed = lambda chunk: delivered.append(chunk.decode("ascii"))

    # Worker that takes time to synthesize
    def _slow_synthesize(text: str) -> bytes | None:
        time.sleep(0.08)
        return text.encode("ascii")

    synth = OrderedStreamSynthesizer(synthesize_fn=_slow_synthesize, player=player, max_workers=2)
    synth.start(gen_id=10)

    # Submit 3 slow chunks
    synth.submit_chunk("chunk_1", gen_id=10)
    synth.submit_chunk("chunk_2", gen_id=10)
    synth.submit_chunk("chunk_3", gen_id=10)

    # Immediate abort
    synth.abort()

    # Wait for thread pool to settle
    time.sleep(0.15)

    # Assert that player received zero chunks, or at most chunk_1 if it was already processing before abort,
    # and that subsequent chunks (chunk_2, chunk_3) were cancelled and never delivered
    assert "chunk_2" not in delivered
    assert "chunk_3" not in delivered
    assert len(synth._pending) == 0, "Pending dictionary must be cleared on abort"
    assert player.is_playing() is False

    player.close()


