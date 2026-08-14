import logging
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

    def initialize(self) -> bool:
        try:
            logger.info(f"Loading ONNX model from {self.model_path}...")
            # Use CPU execution provider for maximum compatibility and low latency
            self.ort_session = ort.InferenceSession(
                self.model_path, 
                providers=['CPUExecutionProvider']
            )
            self.input_name = self.ort_session.get_inputs()[0].name
            
            logger.info("Aura Wake Word model initialized successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize ONNX model: {e}")
            if self.on_error:
                self.on_error(f"Failed to initialize ONNX model: {e}")
            return False

    def process_audio(self, audio_data: bytes, sample_rate: int) -> bool:
        if not self.enabled or self.ort_session is None:
            return False
            
        if self.cooldown_frames > 0:
            self.cooldown_frames -= 1
            return False

        try:
            # Convert raw bytes (16-bit PCM) to float32 numpy array
            chunk_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Resample if necessary (VoiceManager usually provides 16kHz)
            if sample_rate != self.sample_rate:
                # Naive resample, but we assume 16kHz input from VoiceManager
                pass
                
            chunk_len = len(chunk_np)
            
            # Roll buffer and append new chunk
            self.audio_buffer = np.roll(self.audio_buffer, -chunk_len)
            self.audio_buffer[-chunk_len:] = chunk_np
            
            # Only run inference every N chunks to save CPU if desired, 
            # but modern CPUs can run this ONNX model instantly.
            
            # 1. Compute Mel Spectrogram using PyTorch
            waveform = torch.from_numpy(self.audio_buffer).unsqueeze(0)  # Shape: (1, 32000)
            mel_spec = self.mel_transform(waveform)
            log_mel_spec = torch.log(mel_spec + 1e-9).unsqueeze(0) # Shape: (1, 1, 40, 201)
            
            # 2. Run ONNX Inference
            ort_inputs = {self.input_name: log_mel_spec.numpy()}
            ort_outs = self.ort_session.run(None, ort_inputs)
            
            # 3. Apply Sigmoid to logit
            logit = ort_outs[0][0][0]
            probability = float(1.0 / (1.0 + np.exp(-logit)))
            self.last_probability = probability
            
            # 4. Check against threshold
            import os
            threshold = float(os.environ.get("AURA_WAKE_THRESHOLD", 0.60))
            
            if probability >= threshold:
                logger.info(f"[AuraWakeDetector] Wake word detected! (Prob: {probability:.3f} | Threshold: {threshold})")
                
                # Prevent double-triggering for 2 seconds
                self.cooldown_frames = int(self.sample_rate / chunk_len * 2.0)
                
                # Trigger callback
                if self.on_wake_word_detected:
                    self.on_wake_word_detected("Hey Aura")
                    
                return True
                
            return False

        except Exception as e:
            logger.error(f"Error processing audio in AuraWakeDetector: {e}")
            return False

    def is_active(self) -> bool:
        return self.enabled

    def deactivate(self) -> None:
        self.enabled = False
        logger.debug("Aura wake word deactivated")

    def get_status(self) -> dict:
        return {
            "provider": "aura",
            "is_initialized": self.ort_session is not None,
            "enabled": self.enabled,
            "is_active": self.is_active(),
        }
