"""
Speaker Verification & Voiceprint Enrollment Engine
===================================================
Provides fast (<15ms), on-device neural acoustic speaker verification
using VoxCeleb ResNet-34 embeddings to ensure Aura only executes commands
spoken by the enrolled owner.
"""

import os
import time
import logging
import threading
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

import numpy as np

# Torch and torchaudio are lazily imported to keep module startup instantaneous
_torch = None
_kaldi = None


def _get_torch():
    global _torch, _kaldi
    if _torch is None:
        import torch
        import torchaudio.compliance.kaldi as kaldi
        _torch = torch
        _kaldi = kaldi
    return _torch, _kaldi


try:
    import onnxruntime as ort
except ImportError:
    ort = None

logger = logging.getLogger(__name__)

_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
SCHEMA_VERSION: int = 2
MODEL_IDENTIFIER: str = "voxceleb_resnet34"


class SpeakerMatchResult(Enum):
    """Three-tier speaker verification outcome."""
    ACCEPT = "accept"            # High confidence match (user confirmed)
    SOFT_PROMPT = "soft_prompt"  # Ambiguous / lower confidence (was that you? with 3s timeout)
    REJECT = "reject"            # Confirmed different speaker / TV / video
    BYPASS = "bypass"            # No speaker enrolled yet (open mode)


class SpeakerVerificationEngine:
    """
    On-device neural acoustic speaker verification using VoxCeleb ResNet-34 embeddings
    and cosine similarity against the enrolled owner profile.
    """

    _instance: Optional["SpeakerVerificationEngine"] = None
    _instance_lock = threading.Lock()

    def __init__(self, profiles_dir: Optional[Path | str] = None, model_path: Optional[Path | str] = None):
        self.profiles_dir = Path(profiles_dir) if profiles_dir else _PROJECT_ROOT / "Data" / "speaker_profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.profile_path = self.profiles_dir / "owner_voiceprint_v2.npz"
        self.legacy_profile_path = self.profiles_dir / "owner_voiceprint.npy"
        
        # ONNX Model path
        self.model_path = Path(model_path) if model_path else _PROJECT_ROOT / "models" / "speaker" / "voxceleb_resnet34.onnx"
        self._ort_session = None
        self._session_lock = threading.Lock()

        self._lock = threading.RLock()
        self._enrolled_embedding: Optional[np.ndarray] = None
        self._enrolled_exemplars: Optional[np.ndarray] = None
        self._enrolled_registers: Dict[str, np.ndarray] = {}
        self._enrolled_metadata: Dict[str, Any] = {}
        
        # Audio parameters matching VoxCeleb ResNet-34
        self.sample_rate = 16000
        self.num_mel_bins = 80
        # Sensitive vocal threshold to capture soft, low, or quiet speech (configurable via env)
        self.min_rms_energy = float(os.getenv("SPEAKER_MIN_RMS_ENERGY", "0.0025"))
        
        # Real-voice calibrated threshold bands (configurable via .env)
        self.threshold_high = float(os.getenv("SPEAKER_MATCH_HIGH", "0.45"))
        self.threshold_low = float(os.getenv("SPEAKER_MATCH_LOW", "0.30"))
        self.soft_prompt_timeout_s = float(os.getenv("SPEAKER_PROMPT_TIMEOUT", "3.0"))
        
        # Initialize ONNX inference session and load profile if available
        self._ensure_model_loaded()
        self.load_profile()

    @classmethod
    def get_instance(cls) -> "SpeakerVerificationEngine":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _ensure_model_loaded(self) -> bool:
        """Lazily initialize ONNX Runtime inference session."""
        if self._ort_session is not None:
            return True

        with self._session_lock:
            if self._ort_session is not None:
                return True

            if ort is None:
                logger.error("[SpeakerVerification] onnxruntime is not installed.")
                return False

            if not self.model_path.exists():
                logger.info(f"[SpeakerVerification] Downloading speaker model to {self.model_path}...")
                try:
                    from huggingface_hub import hf_hub_download
                    self.model_path.parent.mkdir(parents=True, exist_ok=True)
                    downloaded = hf_hub_download(
                        repo_id="Wespeaker/wespeaker-voxceleb-resnet34",
                        filename="voxceleb_resnet34.onnx",
                        local_dir=str(self.model_path.parent),
                    )
                    self.model_path = Path(downloaded)
                except Exception as e:
                    logger.error(f"[SpeakerVerification] Failed to download speaker model: {e}")
                    return False

            try:
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 1
                opts.inter_op_num_threads = 1
                opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                self._ort_session = ort.InferenceSession(
                    str(self.model_path),
                    sess_options=opts,
                    providers=["CPUExecutionProvider"]
                )
                logger.info(f"[SpeakerVerification] Initialized VoxCeleb ResNet-34 ONNX engine from {self.model_path}")
                return True
            except Exception as e:
                logger.error(f"[SpeakerVerification] Error creating ONNX session: {e}")
                return False

    def load_profile(self) -> bool:
        """Load enrolled owner voiceprint embedding (v2 schema) from disk."""
        with self._lock:
            if self.profile_path.exists():
                try:
                    data = np.load(str(self.profile_path), allow_pickle=True)
                    ver = int(data.get("version", 0))
                    if ver == SCHEMA_VERSION:
                        emb = data["embedding"]
                        norm = np.linalg.norm(emb)
                        if norm > 1e-6:
                            self._enrolled_embedding = (emb / norm).astype(np.float32)
                            
                            # Check for multi-exemplar matrix (low, medium, high variations)
                            if "embeddings" in data and len(data["embeddings"]) > 0:
                                raw_ex = data["embeddings"]
                                norms = np.linalg.norm(raw_ex, axis=1, keepdims=True)
                                norms[norms < 1e-6] = 1.0
                                self._enrolled_exemplars = (raw_ex / norms).astype(np.float32)
                            else:
                                self._enrolled_exemplars = np.expand_dims(self._enrolled_embedding, axis=0)

                            # Check for register centroids (e.g. low, medium, high)
                            self._enrolled_registers = {}
                            if "registers" in data:
                                try:
                                    regs_obj = data["registers"]
                                    regs = regs_obj.item() if hasattr(regs_obj, "item") and callable(regs_obj.item) else dict(regs_obj)
                                    for reg_name, reg_vec in regs.items():
                                        r_norm = np.linalg.norm(reg_vec)
                                        if r_norm > 1e-6:
                                            self._enrolled_registers[str(reg_name)] = (reg_vec / r_norm).astype(np.float32)
                                except Exception:
                                    pass

                            self._enrolled_metadata = {
                                "version": ver,
                                "model": str(data.get("model", MODEL_IDENTIFIER)),
                                "timestamp": float(data.get("timestamp", 0.0)),
                                "sample_count": int(data.get("sample_count", 1)),
                                "exemplar_count": len(self._enrolled_exemplars),
                                "registers": list(self._enrolled_registers.keys()),
                            }
                            logger.info(
                                f"[SpeakerVerification] Loaded v{ver} owner voiceprint from {self.profile_path} "
                                f"({self._enrolled_metadata['sample_count']} samples across {len(self._enrolled_exemplars)} exemplars, "
                                f"registers: {list(self._enrolled_registers.keys()) or ['default']}, model: {self._enrolled_metadata['model']})"
                            )
                            return True
                    else:
                        logger.warning(
                            f"[SpeakerVerification] Outdated voiceprint version (v{ver} vs expected v{SCHEMA_VERSION}). "
                            "Please re-enroll using 'python scripts/enroll_voiceprint.py'."
                        )
                except Exception as e:
                    logger.error(f"[SpeakerVerification] Failed to load voiceprint: {e}")

            # Check legacy v1 profile
            if self.legacy_profile_path.exists():
                logger.warning(
                    "[SpeakerVerification] Incompatible legacy v1 voiceprint profile detected. "
                    "Legacy profiles are invalidated for safety. Please re-enroll via 'python scripts/enroll_voiceprint.py'."
                )

            self._enrolled_embedding = None
            self._enrolled_exemplars = None
            self._enrolled_registers = {}
            self._enrolled_metadata = {}
            return False

    def is_enrolled(self) -> bool:
        """Check if an owner voiceprint (v2) is active and loaded."""
        with self._lock:
            return self._enrolled_embedding is not None

    def compute_embedding(self, audio_data: bytes | np.ndarray) -> Optional[np.ndarray]:
        """
        Compute a normalized 256-dim neural acoustic speaker embedding using VoxCeleb ResNet-34.
        Latency: ~8-15ms on CPU.
        """
        if not self._ensure_model_loaded():
            return None

        try:
            if isinstance(audio_data, bytes):
                audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                audio_np = audio_data.astype(np.float32)
                if np.max(np.abs(audio_np)) > 1.0:
                    audio_np = audio_np / 32768.0

            if len(audio_np.shape) > 1:
                audio_np = np.mean(audio_np, axis=1)

            # Minimum 400ms audio required for stable acoustic statistics
            if len(audio_np) < int(self.sample_rate * 0.4):
                return None

            # Vocal energy pre-gate: ignore silence / background floor (check max vocal frame RMS)
            frame_len = int(self.sample_rate * 0.2)
            hop = int(self.sample_rate * 0.1)
            if len(audio_np) >= frame_len:
                max_frame_rms = max(
                    float(np.sqrt(np.mean(audio_np[i : i + frame_len] ** 2)))
                    for i in range(0, len(audio_np) - frame_len + 1, hop)
                )
            else:
                max_frame_rms = float(np.sqrt(np.mean(audio_np**2)))

            if max_frame_rms < self.min_rms_energy:
                return None

            # 1. Compute 80-bin Kaldi Fbank features (scaled to raw PCM magnitude)
            torch, kaldi = _get_torch()
            waveform = torch.from_numpy(audio_np * 32768.0).unsqueeze(0).float()
            fbank = kaldi.fbank(
                waveform,
                num_mel_bins=self.num_mel_bins,
                frame_length=25,
                frame_shift=10,
                dither=0.0,
                sample_frequency=self.sample_rate,
            )
            # Utterance-level Cepstral Mean Normalization (CMN)
            fbank = fbank - torch.mean(fbank, dim=0, keepdim=True)
            fbank_np = fbank.numpy()

            # 2. Run ONNX Inference
            inp = np.expand_dims(fbank_np, axis=0).astype(np.float32)
            embs = self._ort_session.run(["embs"], {"feats": inp})[0][0]

            # 3. Unit L2 normalize
            norm = np.linalg.norm(embs)
            if norm > 1e-6:
                embs = embs / norm
            return embs.astype(np.float32)

        except Exception as e:
            logger.error(f"[SpeakerVerification] Embedding compute error: {e}")
            return None

    def enroll(
        self,
        audio_samples: List[bytes | np.ndarray] | Dict[str, List[bytes | np.ndarray]],
        registers: Optional[Dict[str, List[bytes | np.ndarray]]] = None,
    ) -> bool:
        """
        Enroll owner voiceprint (v2 schema) from multiple spoken audio samples.
        Supports multi-register enrollment (e.g. low, medium, high vocal pitch/volume).
        Stores both individual exemplar embeddings, per-register centroids, and global centroid.
        """
        sample_dict: Dict[str, List[bytes | np.ndarray]] = {}
        if isinstance(audio_samples, dict):
            sample_dict = audio_samples
        elif registers is not None:
            sample_dict = registers
        else:
            sample_dict = {"default": list(audio_samples)}

        all_embeddings: List[np.ndarray] = []
        register_centroids: Dict[str, np.ndarray] = {}

        for reg_name, samples in sample_dict.items():
            reg_embs = []
            for sample in samples:
                emb = self.compute_embedding(sample)
                if emb is not None:
                    all_embeddings.append(emb)
                    reg_embs.append(emb)
            if reg_embs:
                r_mean = np.mean(reg_embs, axis=0)
                r_norm = np.linalg.norm(r_mean)
                if r_norm > 1e-6:
                    register_centroids[reg_name] = (r_mean / r_norm).astype(np.float32)

        if not all_embeddings:
            logger.error("[SpeakerVerification] No valid embeddings could be computed from audio samples.")
            return False

        with self._lock:
            # Average and normalize for global centroid (backward compatibility)
            mean_emb = np.mean(all_embeddings, axis=0)
            norm = np.linalg.norm(mean_emb)
            if norm > 1e-6:
                mean_emb = mean_emb / norm

            self._enrolled_embedding = mean_emb.astype(np.float32)
            self._enrolled_exemplars = np.array(all_embeddings, dtype=np.float32)
            self._enrolled_registers = register_centroids
            self._enrolled_metadata = {
                "version": SCHEMA_VERSION,
                "model": MODEL_IDENTIFIER,
                "timestamp": time.time(),
                "sample_count": len(all_embeddings),
                "exemplar_count": len(all_embeddings),
                "registers": list(register_centroids.keys()),
            }

            save_payload = {
                "embedding": self._enrolled_embedding,
                "embeddings": self._enrolled_exemplars,
                "version": SCHEMA_VERSION,
                "model": MODEL_IDENTIFIER,
                "timestamp": self._enrolled_metadata["timestamp"],
                "sample_count": len(all_embeddings),
            }
            if register_centroids:
                save_payload["registers"] = np.array(register_centroids, dtype=object)

            np.savez_compressed(
                str(self.profile_path),
                **save_payload,
            )

            # Invalidate legacy v1 profile if present
            if self.legacy_profile_path.exists():
                try:
                    self.legacy_profile_path.unlink()
                except Exception:
                    pass

            logger.info(
                f"[SpeakerVerification] Successfully enrolled owner voiceprint v{SCHEMA_VERSION} "
                f"({len(all_embeddings)} samples across registers: {list(register_centroids.keys())}). Saved to {self.profile_path}"
            )
            return True

    def verify(self, audio_data: bytes | np.ndarray) -> Tuple[SpeakerMatchResult, float]:
        """
        Verify incoming audio against enrolled owner voiceprint using multi-prototype
        nearest-exemplar cosine similarity.

        Returns:
            Tuple of (SpeakerMatchResult, similarity_score)
        """
        with self._lock:
            if self._enrolled_embedding is None:
                # Open bypass mode when no user is enrolled
                return SpeakerMatchResult.BYPASS, 1.0

            emb = self.compute_embedding(audio_data)
            if emb is None:
                # Silent or insufficient vocal energy
                return SpeakerMatchResult.SOFT_PROMPT, 0.0

            # 1. Cosine similarity against global centroid
            mean_sim = float(np.dot(self._enrolled_embedding, emb))

            # 2. Cosine similarity against exemplar embeddings (nearest exemplar matching)
            if self._enrolled_exemplars is not None and len(self._enrolled_exemplars) > 0:
                exemplar_sims = np.dot(self._enrolled_exemplars, emb)
                max_exemplar_sim = float(np.max(exemplar_sims))
                similarity = max(mean_sim, max_exemplar_sim)
            else:
                similarity = mean_sim

            if similarity >= self.threshold_high:
                return SpeakerMatchResult.ACCEPT, similarity
            elif similarity >= self.threshold_low:
                return SpeakerMatchResult.SOFT_PROMPT, similarity
            else:
                return SpeakerMatchResult.REJECT, similarity

    def reset_profile(self) -> bool:
        """Purge enrolled voiceprint profile."""
        with self._lock:
            for p in (self.profile_path, self.legacy_profile_path):
                if p.exists():
                    try:
                        p.unlink()
                    except Exception as e:
                        logger.error(f"[SpeakerVerification] Error deleting profile {p}: {e}")
            self._enrolled_embedding = None
            self._enrolled_exemplars = None
            self._enrolled_registers = {}
            self._enrolled_metadata = {}
            return True
