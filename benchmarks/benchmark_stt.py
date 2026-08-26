import time
import soundfile as sf
import numpy as np
import threading
from voice.models import STTSettings
from voice.stt_manager import FasterWhisperSTTEngine
import logging
import math
try:
    import librosa
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)

settings = STTSettings(model_size="tiny", language="en", sample_rate=16000)
engine = FasterWhisperSTTEngine(settings)

print("Initializing engine...")
engine.initialize()

print("Loading test_speech.wav...")
data, sr = sf.read('test_speech.wav')

if sr != 16000:
    print(f"Resampling from {sr} to 16000...")
    if 'librosa' in globals():
        data = librosa.resample(data, orig_sr=sr, target_sr=16000)
    else:
        # crude resample
        import scipy.signal
        data = scipy.signal.resample(data, int(len(data) * 16000 / sr))
        
# Convert to int16 bytes
audio_data = (data * 32767).astype(np.int16)
audio_bytes = audio_data.tobytes()

print("Testing streaming latency with REAL audio (duration: {:.2f}s)...".format(len(data)/16000))

chunk_size_bytes = 1600 * 2 # 100ms chunks

start_time = time.time()
first_partial_time = None
partial_times = []

def on_partial(confirmed, tentative):
    global first_partial_time
    now = time.time()
    elapsed = now - start_time
    if first_partial_time is None:
        first_partial_time = elapsed
        print(f"[{elapsed:.3f}s] FIRST PARTIAL: confirmed='{confirmed}', tentative='{tentative}'")
    else:
        partial_times.append(now)
        print(f"[{elapsed:.3f}s] PARTIAL: confirmed='{confirmed}', tentative='{tentative}'")

engine.set_callbacks(on_partial, lambda t, d: None, lambda e: None)
engine.reset()

num_chunks = math.ceil(len(audio_bytes) / chunk_size_bytes)
simulated_time = 0.0

# 1. Test normal streaming and Max Window Clamp
for i in range(num_chunks):
    chunk = audio_bytes[i*chunk_size_bytes : (i+1)*chunk_size_bytes]
    engine.process_chunk(chunk)
    time.sleep(0.1)
    simulated_time += 0.1

    # 2. Test race condition by interrupting at exactly 5 seconds
    if i == int(5.0 / 0.1):
        print(f"\n--- TRIGGERING RACE CONDITION AT {simulated_time:.1f}s ---")
        print("Resetting engine while partials are potentially in-flight...")
        engine.reset()
        print("Race condition triggered. Let's see if old text bleeds into new utterance...\n")

end_time = time.time()
print(f"\nStreaming finished in {end_time - start_time:.3f}s")
if first_partial_time:
    print(f"Time to first partial: {first_partial_time:.3f}s")

intervals = []
for i in range(1, len(partial_times)):
    intervals.append(partial_times[i] - partial_times[i-1])

if intervals:
    print(f"Average partial-to-partial interval: {sum(intervals)/len(intervals):.3f}s")
    print(f"Max interval: {max(intervals):.3f}s")
else:
    print("Not enough partials to calculate intervals.")
