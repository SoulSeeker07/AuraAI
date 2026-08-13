#!/usr/bin/env python3
"""
Interactive STT Test

Records 5 seconds of audio from the default microphone and passes it
through the Aura STT Manager (faster-whisper) to transcribe.
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import pyaudio
from src.voice.stt_manager import STTManager, STTSettings, STTProvider
import logging
logging.basicConfig(level=logging.WARNING)
import warnings
warnings.filterwarnings("ignore")

def main():
    print("=======================================")
    print(" AURA INTERACTIVE STT TEST")
    print("=======================================")
    
    # 1. Initialize STT Manager
    print("\n[1/3] Initializing STT Manager (faster-whisper)...")
    settings = STTSettings(provider=STTProvider.FASTER_WHISPER, model_size="tiny")
    manager = STTManager(settings)
    
    if not manager.initialize():
        print("FAIL: Could not initialize STT Manager.")
        sys.exit(1)
        
    print("STT Manager Ready.")
    
    # 2. Record Audio
    RECORD_SECONDS = 5
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    
    p = pyaudio.PyAudio()
    
    print(f"\n[2/3] Opening microphone. Please speak for {RECORD_SECONDS} seconds...")
    try:
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)
    except Exception as e:
        print(f"FAIL: Could not open microphone stream: {e}")
        sys.exit(1)
        
    print("\n*** RECORDING NOW ***")
    frames = []
    
    for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        manager.process_audio(data)
        
    print("*** RECORDING FINISHED ***")
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # 3. Transcribe
    print("\n[3/3] Finalizing transcription...")
    start = time.time()
    transcript = manager.finalize()
    duration = time.time() - start
    
    print("\n=======================================")
    print(f" TRANSCRIPT (took {duration:.2f}s)")
    print("=======================================")
    if transcript.strip():
        print(f"\033[92m{transcript}\033[0m")
    else:
        print("\033[93m[No speech detected]\033[0m")
    print("=======================================\n")

if __name__ == "__main__":
    main()
