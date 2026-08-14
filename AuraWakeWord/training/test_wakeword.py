import os
import sys
import time
import wave
import msvcrt
import threading
from datetime import datetime
from pathlib import Path
import pyaudio
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from AuraWakeWord.runtime.aura_wake_detector import AuraWakeDetector

# Set threshold explicitly for this test if not in environment
if "AURA_WAKE_THRESHOLD" not in os.environ:
    os.environ["AURA_WAKE_THRESHOLD"] = "0.60"

SAMPLE_RATE = 16000
CHUNK_SIZE = 4000  # 250ms chunks

class StandaloneTester:
    def __init__(self):
        self.model_path = str(PROJECT_ROOT / "AuraWakeWord" / "models" / "aura_wakeword.onnx")
        self.output_dir = PROJECT_ROOT / "AuraWakeWord" / "test_recordings"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.detector = AuraWakeDetector(model_path=self.model_path)
        self.detector.on_wake_word_detected = self._on_detect
        
        if not self.detector.initialize():
            print("Failed to initialize detector.")
            sys.exit(1)
            
        self.detector.enabled = True
        
        # Audio stream
        self.pa = pyaudio.PyAudio()
        
        # Stats
        self.stats = {
            "manual_tests": 0,
            "manual_detections": 0,
            "continuous_detections": 0,
            "min_positive_score": 1.0,
            "max_score": 0.0
        }
        
        self.is_detecting = False
        self.post_roll_frames = []
        self.post_roll_remaining = 0
        self.pre_roll_buffer = [] # Store recent chunks
        self.max_pre_roll_chunks = int(2.0 * SAMPLE_RATE / CHUNK_SIZE) # 2 seconds
        
        self.last_detection_time = 0
        self.recording_lock = threading.Lock()
        
    def _on_detect(self, word):
        self.is_detecting = True
        # Request 1 second of post-roll (4 chunks of 250ms)
        self.post_roll_remaining = int(1.0 * SAMPLE_RATE / CHUNK_SIZE)
        self.post_roll_frames = []
        
        prob = getattr(self.detector, 'last_probability', 1.0)
        self.stats["continuous_detections"] += 1
        
        print(f"\n\n>>> WAKE WORD DETECTED! <<<")
        print(f"Score: {prob:.4f}")
        
    def draw_meter(self, audio_data: bytes, prob: float):
        # Calculate volume
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        rms = np.sqrt(np.mean(audio_np**2))
        vol = min(1.0, rms / 10000.0) # Scale arbitrarily for visuals
        
        bars = int(vol * 20)
        meter = "█" * bars + "░" * (20 - bars)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        sys.stdout.write(f"\r[{timestamp}] Mic: {meter} | Score: {prob:.4f}  ")
        sys.stdout.flush()

    def run_continuous(self):
        print("\nStarting continuous listening... Press 'Q' to stop.")
        
        stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        
        self.pre_roll_buffer = []
        
        try:
            while True:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8').lower()
                    if key == 'q':
                        break
                        
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                
                with self.recording_lock:
                    if self.is_detecting:
                        self.post_roll_frames.append(data)
                        self.post_roll_remaining -= 1
                        
                        if self.post_roll_remaining <= 0:
                            # Save the file
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            out_path = self.output_dir / f"{timestamp}_DETECTED.wav"
                            
                            all_data = b"".join(self.pre_roll_buffer + self.post_roll_frames)
                            self._save_wav(out_path, all_data)
                            print(f"Audio saved: {out_path}\nListening...")
                            
                            self.is_detecting = False
                    else:
                        # Keep pre-roll buffer at target length
                        self.pre_roll_buffer.append(data)
                        if len(self.pre_roll_buffer) > self.max_pre_roll_chunks:
                            self.pre_roll_buffer.pop(0)
                            
                # Process detection
                self.detector.process_audio(data, SAMPLE_RATE)
                prob = getattr(self.detector, 'last_probability', 0.0)
                
                # Update max score seen
                if prob > self.stats["max_score"]:
                    self.stats["max_score"] = prob
                    
                if not self.is_detecting:
                    self.draw_meter(data, prob)
                    
        finally:
            stream.stop_stream()
            stream.close()
            print("\nStopped continuous listening.")

    def run_manual(self):
        print("\n--- Manual Test ---")
        print("Get ready to speak...")
        time.sleep(1)
        for i in range(3, 0, -1):
            sys.stdout.write(f"\r{i}...")
            sys.stdout.flush()
            time.sleep(1)
            
        print("\rSpeak now! (Recording 3 seconds...)  ")
        
        stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        
        frames = []
        chunks_to_record = int(3.0 * SAMPLE_RATE / CHUNK_SIZE)
        
        # Reset cooldown and probability
        self.detector.cooldown_frames = 0
        if hasattr(self.detector, 'last_probability'):
            self.detector.last_probability = 0.0
            
        detected = False
        max_prob = 0.0
        
        try:
            for _ in range(chunks_to_record):
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(data)
                
                if self.detector.process_audio(data, SAMPLE_RATE):
                    detected = True
                    
                prob = getattr(self.detector, 'last_probability', 0.0)
                if prob > max_prob:
                    max_prob = prob
                    
        finally:
            stream.stop_stream()
            stream.close()
            
        print("\nRecording complete.")
        
        self.stats["manual_tests"] += 1
        self.stats["max_score"] = max(self.stats["max_score"], max_prob)
        
        if detected:
            self.stats["manual_detections"] += 1
            self.stats["min_positive_score"] = min(self.stats["min_positive_score"], max_prob)
            status = "DETECTED ✅"
            suffix = "_DETECTED"
        else:
            status = "NOT DETECTED ❌"
            suffix = ""
            
        print(f"Model score: {max_prob:.4f}")
        print(f"Result: {status}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = self.output_dir / f"{timestamp}{suffix}.wav"
        self._save_wav(out_path, b"".join(frames))
        print(f"Saved: {out_path}")

    def show_stats(self):
        print("\n--- Statistics ---")
        print(f"Threshold:               {os.environ['AURA_WAKE_THRESHOLD']}")
        print(f"Continuous Detections:   {self.stats['continuous_detections']}")
        print(f"Manual Tests Run:        {self.stats['manual_tests']}")
        print(f"Manual Detections:       {self.stats['manual_detections']}")
        print(f"Max Score Observed:      {self.stats['max_score']:.4f}")
        min_pos = self.stats['min_positive_score']
        print(f"Min Positive Score:      {min_pos:.4f}" if min_pos <= 1.0 else "Min Positive Score:      N/A")
        print("------------------")

    def _save_wav(self, filepath: Path, audio_bytes: bytes):
        with wave.open(str(filepath), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_bytes)

    def menu(self):
        print("=" * 50)
        print("        AURA WAKE WORD STANDALONE TEST")
        print("=" * 50)
        print(f"Model: {self.model_path}")
        print(f"Threshold: {os.environ['AURA_WAKE_THRESHOLD']}")
        print(f"Sample rate: {SAMPLE_RATE} Hz")
        print(f"Device: Microphone (Default)")
        
        while True:
            print("\nCommands:")
            print("  [R] Record test utterance")
            print("  [L] Start continuous listening")
            print("  [S] Show statistics")
            print("  [Q] Quit")
            print("\nSelect command: ", end="", flush=True)
            
            # Wait for key
            key = msvcrt.getch().decode('utf-8').lower()
            print(key.upper())
            
            if key == 'q':
                break
            elif key == 'r':
                self.run_manual()
            elif key == 'l':
                self.run_continuous()
            elif key == 's':
                self.show_stats()

    def cleanup(self):
        self.pa.terminate()

if __name__ == "__main__":
    tester = StandaloneTester()
    try:
        tester.menu()
    except KeyboardInterrupt:
        pass
    finally:
        tester.cleanup()
