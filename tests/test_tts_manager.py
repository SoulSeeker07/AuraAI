import time
import queue
import threading
from unittest.mock import MagicMock, patch
import pytest
import numpy as np

from src.voice.tts_manager import (
    ChunkedStreamPlayer,
    PiperTTSEngine,
    EdgeTTSEngine,
    TTSManger,
    TTSSettings,
    TTSSpeaker,
)
from src.voice.stt_manager import FasterWhisperSTTEngine, STTSettings, STTProvider


def test_chunked_stream_player_lifecycle_and_silence_padding():
    """
    Test that ChunkedStreamPlayer outputs available data and non-blocking silence padding.
    """
    player = ChunkedStreamPlayer(sample_rate=22050, channels=1)
    
    complete_mock = MagicMock()
    interrupt_mock = MagicMock()
    player.set_callbacks(complete_mock, interrupt_mock)
    
    # Mock sounddevice RawOutputStream so tests don't require hardware
    player._stream = MagicMock()
    player._stream.active = True
    
    player.start_utterance()
    assert player.is_playing() is True
    
    # Feed 1024 bytes (512 samples)
    dummy_pcm = b"\x01\x00" * 512
    player.feed(dummy_pcm)
    player.finish()
    
    # Simulate PortAudio callback requesting 1024 samples (2048 bytes)
    outdata = bytearray(2048)
    mv = memoryview(outdata)
    
    player._audio_callback(mv, 1024, None, None)
    
    # The first 1024 bytes should be dummy_pcm, remaining 1024 bytes should be silence (0x00)
    assert outdata[:1024] == dummy_pcm
    assert outdata[1024:] == b"\x00" * 1024
    
    # Wait briefly for off-thread completion dispatch
    time.sleep(0.05)
    complete_mock.assert_called_once()
    interrupt_mock.assert_not_called()


def test_piper_short_utterance_edge_case():
    """
    Test that a single-word utterance ('Yes.') generates and finishes without hanging.
    """
    settings = TTSSettings(speaker=TTSSpeaker.PIPER, fallback_speaker=TTSSpeaker.EDGE_TTS)
    engine = PiperTTSEngine(settings)
    
    # Mock PiperVoice
    engine.voice = MagicMock()
    engine.voice.config.sample_rate = 22050
    
    class FakeAudioChunk:
        audio_int16_bytes = b"\x02\x00" * 256
    
    engine.voice.synthesize.return_value = [FakeAudioChunk()]
    engine.player = MagicMock()
    engine.player.start_utterance.return_value = True
    engine.is_active = True
    
    engine.add_text("Yes.")
    assert engine.speak() is True
    
    # Allow producer thread to run
    time.sleep(0.05)
    engine.player.feed.assert_called_once_with(FakeAudioChunk.audio_int16_bytes)
    engine.player.finish.assert_called_once()


def test_piper_mid_sentence_barge_in_and_immediate_respeak():
    """
    Test that stop() mid-sentence bumps generation_id, aborts playback, and allows
    an immediate second speak() call without self-aborting.
    """
    settings = TTSSettings(speaker=TTSSpeaker.PIPER)
    engine = PiperTTSEngine(settings)
    
    engine.voice = MagicMock()
    engine.voice.config.sample_rate = 22050
    
    # Producer yields chunks slowly to simulate active synthesis
    def slow_synthesize(text):
        for i in range(5):
            time.sleep(0.02)
            chunk = MagicMock()
            chunk.audio_int16_bytes = b"\x03\x00" * 100
            yield chunk
            
    engine.voice.synthesize = slow_synthesize
    engine.player = MagicMock()
    engine.player.start_utterance.return_value = True
    engine.is_active = True
    
    # 1. Start speaking first sentence
    engine.add_text("First long sentence that will be interrupted.")
    engine.speak()
    time.sleep(0.03) # Let 1 chunk emit
    
    # 2. Barge in / stop()
    gen_id_after_start = engine._active_generation_id
    engine.stop()
    assert engine._active_generation_id > gen_id_after_start
    engine.player.abort.assert_called()
    
    # 3. Immediately speak second sentence
    engine.player.reset_mock()
    engine.add_text("Second sentence spoken immediately.")
    assert engine.speak() is True
    
    time.sleep(0.15) # Let second sentence finish
    engine.player.start_utterance.assert_called_once()
    engine.player.finish.assert_called_once()


def test_tts_manager_piper_to_edge_tts_fallback(capsys):
    """
    Test that when Piper engine fails during init or speak, TTSManger automatically
    routes the speech to EdgeTTSEngine and logs a loud warning.
    """
    settings = TTSSettings(
        speaker=TTSSpeaker.PIPER,
        fallback_speaker=TTSSpeaker.EDGE_TTS,
    )
    manager = TTSManger(settings)
    
    # Force Piper init to fail (simulating missing model or ONNX fault)
    with patch.object(PiperTTSEngine, "initialize", return_value=False):
        with patch.object(EdgeTTSEngine, "initialize", return_value=True) as mock_edge_init:
            with patch.object(EdgeTTSEngine, "speak", return_value=True) as mock_edge_speak:
                manager.add_text("Hello from fallback test")
                assert manager.speak() is True
                
                mock_edge_init.assert_called_once()
                mock_edge_speak.assert_called_once()
                
                captured = capsys.readouterr()
                assert "⚠️ [TTS Fallback]" in captured.err


def test_piper_concurrent_load_safety():
    """
    Test concurrency safety: run FasterWhisperSTTEngine processing in parallel with
    PiperTTSEngine streaming synthesis, ensuring zero deadlocks or race conditions.
    """
    stt_settings = STTSettings(provider=STTProvider.FASTER_WHISPER)
    stt_engine = FasterWhisperSTTEngine(stt_settings)
    stt_engine.model = MagicMock()
    stt_engine.model.transcribe.return_value = ([], None)
    
    tts_settings = TTSSettings(speaker=TTSSpeaker.PIPER)
    tts_engine = PiperTTSEngine(tts_settings)
    tts_engine.voice = MagicMock()
    tts_engine.voice.config.sample_rate = 22050
    
    class Chunk:
        audio_int16_bytes = b"\x01\x00" * 512
    tts_engine.voice.synthesize.return_value = [Chunk(), Chunk(), Chunk()]
    tts_engine.player = MagicMock()
    tts_engine.player.start_utterance.return_value = True
    tts_engine.is_active = True
    
    stt_errors = []
    tts_errors = []
    
    def run_stt():
        try:
            for _ in range(10):
                stt_engine.process_chunk(bytes(3200))
                time.sleep(0.01)
        except Exception as e:
            stt_errors.append(e)
            
    def run_tts():
        try:
            for _ in range(5):
                tts_engine.add_text("Concurrent speech test")
                tts_engine.speak()
                time.sleep(0.02)
                tts_engine.stop()
        except Exception as e:
            tts_errors.append(e)
            
    t1 = threading.Thread(target=run_stt)
    t2 = threading.Thread(target=run_tts)
    
    t1.start()
    t2.start()
    
    t1.join(timeout=3.0)
    t2.join(timeout=3.0)
    
    assert not t1.is_alive(), "STT thread hung during concurrency test"
    assert not t2.is_alive(), "TTS thread hung during concurrency test"
    assert len(stt_errors) == 0, f"STT error during concurrent execution: {stt_errors}"
    assert len(tts_errors) == 0, f"TTS error during concurrent execution: {tts_errors}"
