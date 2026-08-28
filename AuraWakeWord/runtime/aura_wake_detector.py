import logging
import sys
import time
import numpy as np
import onnxruntime as ort
import torch
import torchaudio

from src.voice.wake_word import WakeWordEngine

logger = logging.getLogger(__name__)


class AuraWakeDetector(WakeWordEngine):
    """
    Aura's custom local wake word detector powered by ONNX Runtime.
    """

    MAX_CONSECUTIVE_FAILURES = 5

    def __init__(self, model_path: str, sensitivity: float = 0.5, phrase_list: list[str] | None = None):
        super().__init__(sensitivity=sensitivity, phrase_list=phrase_list)
        self.model_path = model_path
        self.ort_session = None
        
        # Audio parameters matching training
        self.sample_rate = 16000
        self.duration_secs = 2.0
        self.num_samples = int(self.sample_rate * self.duration_secs)
        
        # Buffer to hold rolling audio
        self.audio_buffer = np.zeros(self.num_samples, dtype=np.float32)
        
        # 80Hz High-pass filter coefficients for anti-hum & DC removal
        from scipy import signal
        self.hp_b, self.hp_a = signal.butter(2, 80.0 / (self.sample_rate / 2), btype='high')
        self.min_rms_energy = 0.0075  # Minimum energy required before evaluating wake word
        
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

            # 6. Check against calibrated threshold (0.80 default with 3-frame persistence)
            import os
            threshold = float(os.environ.get("AURA_WAKE_THRESHOLD", 0.80))

            now = time.monotonic()
            if probability > 0.10 and (now - self.last_print_time >= self.print_interval_s):
                self.last_print_time = now
                logger.debug(f"[AuraWakeDetector] Debug Score: {probability:.4f} (RMS: {rms_energy:.4f})")
                try:
                    sys.stdout.write(f"\r🎤 Live Score: {probability:.4f} (RMS: {rms_energy:.4f})    ")
                    sys.stdout.flush()
                except Exception:
                    pass

            if probability >= threshold:
                self.consecutive_hits += 1
                if self.consecutive_hits >= 3:
                    try:
                        sys.stdout.write("\r" + " " * 45 + "\r")  # Clear the line
                        sys.stdout.flush()
                    except Exception:
                        pass
                    logger.info(f"[AuraWakeDetector] Wake word detected! (Prob: {probability:.3f} | Threshold: {threshold})")

                    # Prevent double-triggering and reset buffer for next cycle
                    self.cooldown_frames = int(self.sample_rate / chunk_len * 2.0)
                    self.audio_buffer = np.zeros(self.num_samples, dtype=np.float32)
                    self.consecutive_hits = 0

                    # 7. Speaker Voiceprint Gate (if enrolled)
                    try:
                        from src.voice.speaker_verification import SpeakerVerificationEngine, SpeakerMatchResult
                        speaker_engine = SpeakerVerificationEngine.get_instance()
                        match_res, sim_score = speaker_engine.verify(clean_buf)
                        if match_res == SpeakerMatchResult.REJECT:
                            logger.info(f"[SpeakerVerification] Wake word rejected (sim={sim_score:.2f} < {speaker_engine.threshold_low}) — ignoring background / non-owner voice.")
                            self.audio_buffer = np.zeros(self.num_samples, dtype=np.float32)
                            self.consecutive_hits = 0
                            self.cooldown_frames = int(self.sample_rate / chunk_len * 1.5)
                            return False
                    except Exception as ve:
                        logger.debug(f"[SpeakerVerification] Verification check note: {ve}")

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
            "is_active": self.is_active(),
        }
