import logging
import sys
import time
import numpy as np
import onnxruntime as ort
import torch
import torchaudio

try:
    from voice.wake_word import WakeWordEngine
except ImportError:
    from src.voice.wake_word import WakeWordEngine

logger = logging.getLogger(__name__)


class AuraWakeDetector(WakeWordEngine):
    """
    Aura's custom local wake word detector powered by ONNX Runtime.
    """

    MAX_CONSECUTIVE_FAILURES = 5

    def __init__(self, model_path: str, sensitivity: float = 0.5, phrase_list: list[str] | None = None, required_hits: int = 5):
        super().__init__(sensitivity=sensitivity, phrase_list=phrase_list)
        self.model_path = model_path
        self.ort_session = None
        import os
        self.required_hits = int(os.environ.get("AURA_WAKE_REQUIRED_HITS", str(required_hits)))
        
        # Audio parameters matching training
        self.sample_rate = 16000
        self.duration_secs = 2.0
        self.num_samples = int(self.sample_rate * self.duration_secs)
        
        # Buffer to hold rolling audio
        self.audio_buffer = np.zeros(self.num_samples, dtype=np.float32)
        
        # 80Hz High-pass filter coefficients for anti-hum & DC removal
        from scipy import signal
        self.hp_b, self.hp_a = signal.butter(2, 80.0 / (self.sample_rate / 2), btype='high')
        self.min_rms_energy = 0.0030  # Sensitive vocal energy threshold
        
        # Mel Spectrogram parameters matching training
        self.mel_transform = torchaudio.transforms.MelSpectrogram(
            sample_rate=self.sample_rate,
            n_fft=400,
            hop_length=160,
            n_mels=40
        )
        
        # To avoid triggering repeatedly on the same wake word
        self.cooldown_frames = 0
        self.frames_since_trigger = 0

        # Failure & Throttling tracking
        self.consecutive_hits = 0
        self.consecutive_failures = 0
        self.last_print_time = 0.0
        self.print_interval_s = 0.3

    def initialize(self) -> bool:
        try:
            logger.info(f"Loading ONNX model from {self.model_path}...")
            # Use CPU execution provider for maximum compatibility and low latency
            self.ort_session = ort.InferenceSession(
                self.model_path, 
                providers=['CPUExecutionProvider']
            )
            self.input_name = self.ort_session.get_inputs()[0].name
            self.audio_buffer = np.zeros(self.num_samples, dtype=np.float32)
            
            logger.info("Aura Wake Word model initialized successfully.")
            return True
        except Exception as e:
            logger.exception(f"Failed to initialize ONNX model: {e}")
            if self.on_error:
                self.on_error(f"Failed to initialize ONNX model: {e}")
            return False

    def process_audio(self, audio_data: bytes, sample_rate: int) -> bool:
        if not self.enabled or self.ort_session is None:
            return False
            
        try:
            # Convert raw bytes (16-bit PCM) to float32 numpy array
            chunk_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            chunk_len = len(chunk_np)
            if chunk_len == 0:
                return False

            # Roll buffer and append new chunk
            self.audio_buffer = np.roll(self.audio_buffer, -chunk_len)
            self.audio_buffer[-chunk_len:] = chunk_np
            
            # Now check cooldown before running heavy inference
            if self.cooldown_frames > 0:
                self.cooldown_frames -= 1
                return False
            
            # 1. Clean audio buffer: Remove DC offset and apply 80Hz High-Pass filter
            from scipy import signal
            clean_buf = self.audio_buffer - np.mean(self.audio_buffer)
            clean_buf = signal.lfilter(self.hp_b, self.hp_a, clean_buf).astype(np.float32)

            # 2. Energy Pre-Gate: If ambient sound is below human vocal threshold (RMS < min_rms_energy),
            # force score to 0.0 to prevent DC hum / low-frequency room rumble from inflating score
            rms_energy = float(np.sqrt(np.mean(clean_buf**2)))
            if rms_energy < self.min_rms_energy:
                self.last_probability = 0.0
                self.consecutive_hits = 0
                self.consecutive_failures = 0
                return False

            # 3. Compute Mel Spectrogram using PyTorch
            waveform = torch.from_numpy(clean_buf).unsqueeze(0)  # Shape: (1, 32000)
            mel_spec = self.mel_transform(waveform)
            log_mel_spec = torch.log(mel_spec + 1e-9).unsqueeze(0)  # Shape: (1, 1, 40, 201)

            # 4. Run ONNX Inference
            ort_inputs = {self.input_name: log_mel_spec.numpy()}
            ort_outs = self.ort_session.run(None, ort_inputs)

            # 5. Apply Sigmoid to logit
            logit = ort_outs[0][0][0]
            probability = float(1.0 / (1.0 + np.exp(-logit)))
            self.last_probability = probability

            # 6. Check against calibrated threshold
            # If enrolled, speaker verification filters TTS voice, allowing natural 0.80 threshold.
            # If not enrolled, elevate to 0.88 (4-frame persistence) as acoustic fallback guard.
            import os
            is_speaking = getattr(self, "is_speaking", False)
            has_voiceprint = False
            try:
                try:
                    from voice.speaker_verification import SpeakerVerificationEngine
                except ImportError:
                    from src.voice.speaker_verification import SpeakerVerificationEngine
                has_voiceprint = SpeakerVerificationEngine.get_instance().is_enrolled()
            except Exception:
                pass

            if is_speaking and not has_voiceprint:
                threshold = float(os.environ.get("AURA_TTS_WAKE_THRESHOLD", 0.88))
                required_hits = int(os.environ.get("AURA_TTS_WAKE_REQUIRED_HITS", "3"))
            else:
                threshold = float(os.environ.get("AURA_WAKE_THRESHOLD", 0.82))
                required_hits = int(os.environ.get("AURA_WAKE_REQUIRED_HITS", str(getattr(self, "required_hits", 5))))

            now = time.monotonic()
            if probability > 0.10 and (now - self.last_print_time >= self.print_interval_s):
                self.last_print_time = now
                logger.debug(f"[AuraWakeDetector] Debug Score: {probability:.4f} (RMS: {rms_energy:.4f}, speaking={is_speaking})")

            if probability >= threshold:
                self.consecutive_hits += 1
                if self.consecutive_hits >= required_hits:
                    # 7. Speaker Voiceprint Gate (if enrolled)
                    try:
                        try:
                            from voice.speaker_verification import SpeakerVerificationEngine, SpeakerMatchResult
                        except ImportError:
                            from src.voice.speaker_verification import SpeakerVerificationEngine, SpeakerMatchResult
                        speaker_engine = SpeakerVerificationEngine.get_instance()
                        if speaker_engine.is_enrolled():
                            match_res, sim_score = speaker_engine.verify(clean_buf)
                            if match_res == SpeakerMatchResult.REJECT:
                                logger.debug(f"[SpeakerVerification] Wake candidate below threshold (sim={sim_score:.2f} < {speaker_engine.threshold_low})")
                                if self.consecutive_hits >= 12:
                                    logger.info(f"[SpeakerVerification] Wake word candidate rejected (sim={sim_score:.2f} < {speaker_engine.threshold_low}) — non-owner voice.")
                                    try:
                                        from gui.signals import app_signals
                                        if hasattr(app_signals, "speaker_rejected"):
                                            app_signals.speaker_rejected.emit(sim_score)
                                    except Exception:
                                        pass
                                    self.consecutive_hits = 0
                                return False
                    except Exception as ve:
                        logger.debug(f"[SpeakerVerification] Verification check note: {ve}")

                    try:
                        sys.stdout.write("\r" + " " * 45 + "\r")  # Clear the line
                        sys.stdout.flush()
                    except Exception:
                        pass
                    logger.info(f"[AuraWakeDetector] Wake word detected! (Prob: {probability:.3f} | Threshold: {threshold} | Speaking: {is_speaking})")

                    # Prevent double-triggering and reset buffer for next cycle
                    self.cooldown_frames = int(self.sample_rate / chunk_len * 2.0)
                    self.audio_buffer = np.zeros(self.num_samples, dtype=np.float32)
                    self.consecutive_hits = 0

                    # Auto-save triggered positive sample into existing dataset folder (AuraWakeWord/dataset/raw/positive)
                    if os.environ.get("SAVE_WAKE_WORD_SAMPLES", "false").lower() == "true":
                        self._save_positive_sample_deferred(clean_buf, post_delay_s=0.5)

                    # Trigger callback
                    if self.on_wake_word_detected:
                        self.on_wake_word_detected("Hey Aura")

                    self.consecutive_failures = 0
                    return True
            else:
                self.consecutive_hits = 0

            self.consecutive_failures = 0
            return False

        except Exception as e:
            self.consecutive_failures += 1
            logger.exception(f"[AuraWakeDetector] Error processing audio (failure {self.consecutive_failures}/{self.MAX_CONSECUTIVE_FAILURES}): {e}")
            if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                if self.on_error:
                    self.on_error(f"AuraWakeDetector reached {self.consecutive_failures} consecutive failures: {e}")
            return False

    def reset(self) -> None:
        """Reset internal rolling audio buffers and hit tracking."""
        self.audio_buffer = np.zeros(self.num_samples, dtype=np.float32)
        self.consecutive_hits = 0
        self.cooldown_frames = 0
        self.last_probability = 0.0

    def is_active(self) -> bool:
        return self.enabled

    def deactivate(self) -> None:
        self.enabled = False
        self.reset()
        logger.debug("Aura wake word deactivated")

    def get_status(self) -> dict:
        return {
            "provider": "aura",
            "is_initialized": self.ort_session is not None,
            "enabled": self.enabled,
            "last_probability": self.last_probability,
            "phrase_count": len(self.phrase_list),
            "is_active": self.is_active(),
        }

    def _save_positive_sample_deferred(self, pre_trigger_buf: np.ndarray, post_delay_s: float = 0.5) -> None:
        """Collect post-trigger microphone audio so the end of the word ('-ra') is never truncated."""
        import threading
        import time

        pre_snapshot = np.copy(pre_trigger_buf)

        def _worker():
            try:
                time.sleep(post_delay_s)
                # Grab the post-trigger samples added to self.audio_buffer during the 0.5s delay
                post_samples_count = int(self.sample_rate * post_delay_s)
                post_snapshot = np.copy(self.audio_buffer[-post_samples_count:])

                # Combine pre-trigger (2.0s) + post-trigger (0.5s)
                full_combined = np.concatenate([pre_snapshot, post_snapshot])
                self._save_positive_sample(full_combined)
            except Exception as e:
                logger.debug(f"[AuraWakeDetector] Deferred save error: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _save_positive_sample(self, audio_buf: np.ndarray) -> None:
        """Auto-save triggered positive wake word audio into the existing dataset folder."""
        try:
            import wave
            import numpy as np
            from datetime import datetime
            from pathlib import Path

            # Exact existing project folder: AuraWakeWord/dataset/raw/positive
            output_dir = Path(__file__).resolve().parents[1] / "dataset" / "raw" / "positive"
            if not output_dir.exists():
                output_dir.mkdir(parents=True, exist_ok=True)

            # 1. Detect vocal speech start (20ms sliding RMS energy)
            frame_len = int(self.sample_rate * 0.02)  # 320 samples (20ms)
            n_frames = len(audio_buf) // frame_len
            rms_vals = np.array([
                np.sqrt(np.mean(audio_buf[i * frame_len : (i + 1) * frame_len] ** 2))
                for i in range(n_frames)
            ])

            # Find first vocal frame exceeding vocal threshold (0.005)
            vocal_indices = np.where(rms_vals > 0.005)[0]
            if len(vocal_indices) > 0:
                # Start 350ms before vocal onset to capture full initial consonant ("Au-", "H-")
                pre_roll_samples = int(self.sample_rate * 0.35)
                start_sample = max(0, (vocal_indices[0] * frame_len) - pre_roll_samples)
                audio_clip = audio_buf[start_sample:]
            else:
                audio_clip = audio_buf

            # Ensure minimum clip length of 1.5s for model compatibility
            min_samples = int(self.sample_rate * 1.5)
            if len(audio_clip) < min_samples:
                audio_clip = audio_buf[-min_samples:] if len(audio_buf) >= min_samples else audio_buf

            # 2. Normalize peak volume to 90% full scale so voice is crisp
            max_amp = float(np.max(np.abs(audio_clip)))
            if max_amp > 1e-4:
                audio_clip = (audio_clip / max_amp) * 0.90

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"positive_{timestamp}.wav"
            filepath = output_dir / filename

            # Convert float32 clean buffer (-1.0 to 1.0) back to 16-bit PCM WAV
            int16_pcm = (audio_clip * 32767.0).clip(-32768.0, 32767.0).astype(np.int16)

            with wave.open(str(filepath), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit = 2 bytes
                wf.setframerate(self.sample_rate)
                wf.writeframes(int16_pcm.tobytes())

            logger.info(f"[AuraWakeDetector] Auto-saved aligned positive sample: '{filename}' ({len(audio_clip)/self.sample_rate:.2f}s)")
        except Exception as se:
            logger.debug(f"[AuraWakeDetector] Sample auto-save note: {se}")
