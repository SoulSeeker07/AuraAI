import time
import soundfile as sf
import numpy as np
import threading
import logging
import math

from voice.models import STTSettings
from voice.stt_manager import FasterWhisperSTTEngine

logging.basicConfig(level=logging.ERROR)

# Monkey-patch FasterWhisperSTTEngine to log window math
original_process_chunk = FasterWhisperSTTEngine.process_chunk
def mock_process_chunk(self, audio_data: bytes) -> str:
    original_process_chunk(self, audio_data)
    buffer_duration_s = sum(len(b) for b in self._audio_buffer) / (self.settings.sample_rate * 2)
    safety_margin_s = 1.0
    window_start_s = max(0.0, self._stabilizer.confirmed_audio_offset_s - safety_margin_s)
    window_start_s = max(window_start_s, buffer_duration_s - self._max_window_s)
    print(f"[Buffer: {buffer_duration_s:.1f}s] Window Start: {window_start_s:.1f}s (Confirmed: {self._stabilizer.confirmed_audio_offset_s:.1f}s)")
    return ""
FasterWhisperSTTEngine.process_chunk = mock_process_chunk

# Monkey-patch _run_partial_transcribe to force the race condition
original_run_partial = FasterWhisperSTTEngine._run_partial_transcribe
def mock_run_partial(self, audio_snapshot: bytes, offset_s: float, utterance_id: int) -> None:
    # Add artificial delay to GUARANTEE overlap with reset
    time.sleep(0.5)
    if self._utterance_id != utterance_id:
        print(f"\n>>> RACE CONDITION AVERTED! Discarding result from utterance {utterance_id} because current is {self._utterance_id} <<<\n")
    original_run_partial(self, audio_snapshot, offset_s, utterance_id)
FasterWhisperSTTEngine._run_partial_transcribe = mock_run_partial

# Monkey-patch Stabilizer to simulate 0% agreement (worst-case audio)
from voice.stt_manager import LocalAgreementStabilizer
original_update = LocalAgreementStabilizer.update
def mock_update(self, words_with_timestamps):
    res = original_update(self, words_with_timestamps)
    # FORCE the confirmed offset back to 0 to simulate total disagreement
    self.confirmed_audio_offset_s = 0.0
    return res
LocalAgreementStabilizer.update = mock_update

settings = STTSettings(model_size="tiny", language="en", sample_rate=16000)
engine = FasterWhisperSTTEngine(settings)
engine.initialize()

print("Loading test_speech.wav...")
data, sr = sf.read('test_speech.wav')
audio_data = (data * 32767).astype(np.int16)
audio_bytes = audio_data.tobytes()
chunk_size_bytes = 1600 * 2 # 100ms chunks

def on_partial(confirmed, tentative):
    pass
engine.set_callbacks(on_partial, lambda t, d: None, lambda e: None)
engine.reset()

num_chunks = math.ceil(len(audio_bytes) / chunk_size_bytes)
simulated_time = 0.0

print("\n--- STARTING TEST ---")
for i in range(num_chunks):
    chunk = audio_bytes[i*chunk_size_bytes : (i+1)*chunk_size_bytes]
    engine.process_chunk(chunk)
    time.sleep(0.1)
    simulated_time += 0.1

    if i == int(5.0 / 0.1):
        print(f"\n--- TRIGGERING RESET AT {simulated_time:.1f}s ---")
        engine.reset()

print("--- END TEST ---")
