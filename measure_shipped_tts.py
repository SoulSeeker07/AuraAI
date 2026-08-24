import os
import time
from voice.tts_manager import TTSManger, TTSSettings, TTSSpeaker

os.environ["PIPER_MODEL_PATH"] = "models/tts/piper/en_US-lessac-medium.onnx"

sentences = [
    "Yes, I understand.",
    "Hello! This is a test of the shipped Piper streaming TTS implementation.",
    "Streaming audio chunks in real time allows the system to begin playback almost immediately, completely transforming the responsiveness of voice interactions."
]

settings = TTSSettings(speaker=TTSSpeaker.PIPER, fallback_speaker=TTSSpeaker.EDGE_TTS)
mgr = TTSManger(settings)
mgr.initialize()

orig_cb = mgr.engine.player._audio_callback

print("=== Shipped Piper TTFB Across Sentence Lengths ===")
for text in sentences:
    first_audible_time = None
    t0 = None

    def instrumented_cb(outdata, frames, time_info, status):
        global first_audible_time, t0
        orig_cb(outdata, frames, time_info, status)
        if first_audible_time is None and t0 is not None:
            if any(b != 0 for b in outdata):
                first_audible_time = time.perf_counter() - t0

    mgr.engine.player._audio_callback = instrumented_cb

    mgr.add_text(text)
    t0 = time.perf_counter()
    mgr.speak()

    time.sleep(3.5)
    mgr.stop()

    assert mgr.fallback_engine is None, "Fallback should not be active"
    assert mgr.get_status()["speaker"] == "piper"
    print(f"Text ({len(text):3d} chars): '{text[:35]}...' -> Measured TTFB: {first_audible_time*1000:.1f} ms")
