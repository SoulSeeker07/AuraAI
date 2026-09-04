"""
Tests for Neural Speaker Verification & Voiceprint Gating (v2)
==============================================================
Tests VoxCeleb ResNet-34 speaker verification on real speech audio samples,
legacy profile invalidation, and active-turn gating in VoiceManager.
"""

import glob
import time
import wave
import numpy as np
import pytest
import soundfile as sf
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.voice.speaker_verification import (
    SpeakerVerificationEngine,
    SpeakerMatchResult,
    SCHEMA_VERSION,
)
from src.voice.voice_manager import VoiceManager
from src.voice.models import ConversationState, VoiceContext


def _load_wav(path: Path | str) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        frames = wf.readframes(wf.getnframes())
        return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


@pytest.fixture
def temp_profiles_dir(tmp_path):
    prof_dir = tmp_path / "speaker_profiles"
    prof_dir.mkdir(parents=True, exist_ok=True)
    return prof_dir


class TestSpeakerVerificationEngine:

    def test_embedding_computation_shape_and_norm(self, temp_profiles_dir):
        engine = SpeakerVerificationEngine(profiles_dir=temp_profiles_dir)
        
        pos_files = sorted(glob.glob("AuraWakeWord/dataset/raw/positive/*.wav"))
        if pos_files:
            audio = _load_wav(pos_files[0])
        else:
            t = np.linspace(0, 1.0, 16000, endpoint=False)
            audio = (np.sin(2 * np.pi * 300 * t) * 0.3).astype(np.float32)

        emb = engine.compute_embedding(audio)
        assert emb is not None
        assert emb.shape == (256,)
        assert np.isclose(np.linalg.norm(emb), 1.0, atol=1e-4)

    def test_silence_returns_none(self, temp_profiles_dir):
        engine = SpeakerVerificationEngine(profiles_dir=temp_profiles_dir)
        silence = np.zeros(16000, dtype=np.int16).tobytes()
        emb = engine.compute_embedding(silence)
        assert emb is None

    def test_legacy_v1_profile_invalidation(self, temp_profiles_dir):
        legacy_path = temp_profiles_dir / "owner_voiceprint.npy"
        dummy_v1_emb = np.random.randn(192).astype(np.float32)
        np.save(str(legacy_path), dummy_v1_emb)

        engine = SpeakerVerificationEngine(profiles_dir=temp_profiles_dir)
        assert not engine.is_enrolled()
        res, sim = engine.verify(np.random.randn(16000).astype(np.float32))
        assert res == SpeakerMatchResult.BYPASS

    def test_enrollment_and_real_speech_disambiguation(self, temp_profiles_dir):
        pos_files = sorted(glob.glob("AuraWakeWord/dataset/raw/positive/*.wav"))
        if len(pos_files) < 4:
            pytest.skip("Insufficient dataset positive samples for real voice test")

        engine = SpeakerVerificationEngine(profiles_dir=temp_profiles_dir)
        assert not engine.is_enrolled()

        # Enroll on first 3 real positive recordings
        enroll_samples = [_load_wav(p) for p in pos_files[:3]]
        ok = engine.enroll(enroll_samples)
        assert ok is True
        assert engine.is_enrolled() is True
        assert engine.profile_path.exists()

        # Test against 4th positive recording (same owner)
        test_owner_wav = _load_wav(pos_files[3])
        res_owner, sim_owner = engine.verify(test_owner_wav)
        assert res_owner in (SpeakerMatchResult.ACCEPT, SpeakerMatchResult.SOFT_PROMPT)
        assert sim_owner >= engine.threshold_low

        # Test against real distinct non-owner voices
        for audio_path in ["scratch/test_other_female.mp3", "scratch/test_other_male.mp3", "scratch/test_other_indian_female.mp3"]:
            if Path(audio_path).exists():
                data, sr = sf.read(audio_path)
                res_other, sim_other = engine.verify(data)
                assert res_other == SpeakerMatchResult.REJECT
                assert sim_other < engine.threshold_low

    def test_reset_profile(self, temp_profiles_dir):
        engine = SpeakerVerificationEngine(profiles_dir=temp_profiles_dir)
        pos_files = sorted(glob.glob("AuraWakeWord/dataset/raw/positive/*.wav"))
        if pos_files:
            engine.enroll([_load_wav(pos_files[0])])
            assert engine.is_enrolled()
            engine.reset_profile()
            assert not engine.is_enrolled()
            assert not engine.profile_path.exists()

    def test_multi_register_enrollment_and_reloading(self, temp_profiles_dir):
        pos_files = sorted(glob.glob("AuraWakeWord/dataset/raw/positive/*.wav"))
        if len(pos_files) < 4:
            pytest.skip("Insufficient dataset positive samples for multi-register test")

        engine = SpeakerVerificationEngine(profiles_dir=temp_profiles_dir)
        
        # Group into multi-register dictionary: medium, low, high
        register_samples = {
            "medium": [_load_wav(pos_files[0]), _load_wav(pos_files[1])],
            "low": [_load_wav(pos_files[2])],
            "high": [_load_wav(pos_files[3])],
        }

        ok = engine.enroll(register_samples)
        assert ok is True
        assert engine.is_enrolled() is True
        assert engine._enrolled_exemplars is not None
        assert engine._enrolled_exemplars.shape == (4, 256)
        assert "low" in engine._enrolled_registers
        assert "medium" in engine._enrolled_registers
        assert "high" in engine._enrolled_registers

        # Reload from disk and verify persistence
        fresh_engine = SpeakerVerificationEngine(profiles_dir=temp_profiles_dir)
        assert fresh_engine.is_enrolled() is True
        assert fresh_engine._enrolled_exemplars.shape == (4, 256)
        assert set(fresh_engine._enrolled_registers.keys()) == {"medium", "low", "high"}
        assert fresh_engine._enrolled_metadata["sample_count"] == 4

        # Test verification uses nearest exemplar (high similarity to enrolled sample)
        res, sim = fresh_engine.verify(_load_wav(pos_files[2]))
        assert res in (SpeakerMatchResult.ACCEPT, SpeakerMatchResult.SOFT_PROMPT)
        assert sim >= fresh_engine.threshold_high

    def test_quiet_voice_low_rms_embedding(self, temp_profiles_dir):
        pos_files = sorted(glob.glob("AuraWakeWord/dataset/raw/positive/*.wav"))
        if not pos_files:
            pytest.skip("Requires positive dataset sample")

        engine = SpeakerVerificationEngine(profiles_dir=temp_profiles_dir)
        raw_audio = _load_wav(pos_files[0])

        # Scale down audio to simulate soft/quiet voice (RMS around 0.003)
        current_rms = float(np.sqrt(np.mean(raw_audio**2)))
        quiet_audio = raw_audio * (0.0035 / (current_rms + 1e-6))
        quiet_rms = float(np.sqrt(np.mean(quiet_audio**2)))
        assert 0.0028 <= quiet_rms <= 0.0042

        # Sensitive gate (min_rms_energy = 0.0025) must capture and compute embedding
        emb = engine.compute_embedding(quiet_audio)
        assert emb is not None
        assert emb.shape == (256,)
        assert np.isclose(np.linalg.norm(emb), 1.0, atol=1e-4)


class TestVoiceManagerSpeakerGating:

    def test_active_turn_rejected_non_owner_voice(self, temp_profiles_dir):
        engine = SpeakerVerificationEngine.get_instance()
        engine.profiles_dir = temp_profiles_dir
        engine.profile_path = temp_profiles_dir / "owner_voiceprint_v2.npz"

        pos_files = sorted(glob.glob("AuraWakeWord/dataset/raw/positive/*.wav"))
        if pos_files:
            engine.enroll([_load_wav(p) for p in pos_files[:3]])
        else:
            t = np.linspace(0, 2.0, 32000, endpoint=False)
            dummy_owner = ((np.sin(2 * np.pi * 130 * t) + 0.5 * np.sin(2 * np.pi * 260 * t)) * 0.4 * 32768).astype(np.int16).tobytes()
            engine.enroll([dummy_owner])

        assert engine.is_enrolled()

        vm = VoiceManager()
        stt_results = []
        vm.on_stt_result = lambda ctx: stt_results.append(ctx)

        # Set up active listening turn with fresh timestamp
        vm.state = ConversationState.ACTIVE_LISTENING
        vm._speech_started_in_turn = True
        vm._active_listening_start_time = time.time()
        vm._turn_audio_chunks = []

        # Feed non-owner audio (real other speech)
        if Path("scratch/test_other_female.mp3").exists():
            data, _ = sf.read("scratch/test_other_female.mp3")
            data_pcm = (data * 32768.0).astype(np.int16).tobytes()
        else:
            data_pcm = np.random.randn(32000).astype(np.int16).tobytes()

        vm.process_audio(data_pcm, 16000)

        # Finalize STT
        vm.stt_manager.finalize = MagicMock(return_value="open browser please")
        vm._finalize_stt()

        # Transcript should be REJECTED and dropped (not dispatched to on_stt_result)
        assert len(stt_results) == 0
        assert vm.state == ConversationState.IDLE

    def test_active_turn_accepted_owner_voice(self, temp_profiles_dir):
        engine = SpeakerVerificationEngine.get_instance()
        engine.profiles_dir = temp_profiles_dir
        engine.profile_path = temp_profiles_dir / "owner_voiceprint_v2.npz"

        pos_files = sorted(glob.glob("AuraWakeWord/dataset/raw/positive/*.wav"))
        if not pos_files:
            pytest.skip("Requires positive dataset samples for owner voice verification test")

        engine.enroll([_load_wav(p) for p in pos_files[:3]])
        assert engine.is_enrolled()

        vm = VoiceManager()
        stt_results = []
        vm.on_stt_result = lambda ctx: stt_results.append(ctx)

        # Set up active listening turn with fresh timestamp
        vm.state = ConversationState.ACTIVE_LISTENING
        vm._speech_started_in_turn = True
        vm._active_listening_start_time = time.time()
        vm._turn_audio_chunks = []

        # Feed owner voice audio (4th positive sample)
        owner_wav = _load_wav(pos_files[3])
        owner_pcm = (owner_wav * 32768.0).astype(np.int16).tobytes()
        vm.process_audio(owner_pcm, 16000)

        # Finalize STT
        vm.stt_manager.finalize = MagicMock(return_value="what is the weather")
        vm._finalize_stt()

        # Transcript should be ACCEPTED and dispatched
        assert len(stt_results) == 1
        assert stt_results[0].transcript == "what is the weather"
