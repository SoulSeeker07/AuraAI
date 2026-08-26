from faster_whisper import WhisperModel
import sys

# Create a 1 second silent numpy array
import numpy as np
audio = np.zeros(16000, dtype=np.float32)

model = WhisperModel("tiny", device="cpu", compute_type="int8")
segments, info = model.transcribe(audio, language="en", beam_size=5)

for segment in segments:
    print(f"Text: {segment.text}")
    print(f"No speech prob: {segment.no_speech_prob}")
