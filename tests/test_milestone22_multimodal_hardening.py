"""
Milestone 22: Multimodal Voice & Vision Subsystems Hardening Test Suite
Location: tests/test_milestone22_multimodal_hardening.py

Validates the 6-Gate Definition of Done for M22:
- G1: Live Orchestration (Speech & Vision through MasterOrchestrator)
- G2: Vision Grounding (Screen capture -> UI elements -> WorldSnapshot coordinates)
- G3: Voice Reliability & Degradation (STT/TTS fallbacks & explicit unavailable states)
- G4: Device Privacy & Containment (Pre-capture fail-closed & sensitive window default-BLOCK)
- G5: Multimodal Memory Provenance (CognitiveMemory consolidation with full provenance)
- G6: Capability Governance & Non-regression
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pytest

from core.backends.adapters.vision_backend import VisionEngineBackend
from core.backends.adapters.voice_backend import VoiceEngineBackend
from core.backends.backend_registry import BackendRegistry
from core.capabilities.capability_registry import CapabilityRegistry
from core.capabilities.providers.multimodal_provider import MultimodalCapabilityProvider
from core.orchestration.autonomy_mode import ActionRisk
from core.orchestration.decision_engine import DecisionEngine, IntentType
from core.orchestration.master_orchestrator import MasterOrchestrator
from core.orchestration.task_decomposer import TaskDecomposer
from desktop.native.security.device_privacy import (
    DevicePrivacyEngine,
    DeviceType,
    PermissionState,
    SensitiveWindowDetector,
    SensitiveWindowPolicy,
)
from memory.cognitive_memory import CognitiveMemoryEngine, MemoryType, ProvenanceSource
from memory.consolidation_engine import ConsolidationEngine


class TestMilestone22MultimodalHardening(unittest.TestCase):
    """6-Gate verification suite for Milestone 22 Multimodal Subsystems."""

    def setUp(self) -> None:
        # Reset singletons for pristine test isolation
        DevicePrivacyEngine.reset_instance()
        CapabilityRegistry.reset_instance()
        BackendRegistry._instance = None
        self.privacy = DevicePrivacyEngine.get_instance()
        self.backend_registry = BackendRegistry()
        self.orchestrator = MasterOrchestrator(backend_registry=self.backend_registry)
        self.cap_registry = CapabilityRegistry.get_instance()

    def tearDown(self) -> None:
        DevicePrivacyEngine.reset_instance()
        CapabilityRegistry.reset_instance()
        BackendRegistry._instance = None

    # ═════════════════════════════════════════════════════════════════════════
    #  GATE G1: Live Orchestration (Speech & Vision Pipeline)
    # ═════════════════════════════════════════════════════════════════════════

    def test_g1_live_vision_pipeline_orchestration(self) -> None:
        """Verify visual query executes through MasterOrchestrator to VisionEngineBackend."""
        self.privacy.set_device_permission(DeviceType.SCREEN_CAPTURE, PermissionState.ALLOWED)

        goal = "describe screen"
        result = asyncio.run(self.orchestrator.process_request_async(goal))

        self.assertTrue(result.success, f"Expected successful vision execution, got error: {result.warnings} observations: {result.observations}")
        self.assertIn(result.planner, ("vision", "cognitive_orchestrator"))
        self.assertTrue(any("visual" in obs.lower() or "desktop" in obs.lower() for obs in result.observations))
        self.assertIn("vision_captures", result.data)

    def test_g1_live_voice_pipeline_orchestration(self) -> None:
        """Verify voice command executes through MasterOrchestrator to VoiceEngineBackend."""
        self.privacy.set_device_permission(DeviceType.MICROPHONE, PermissionState.ALLOWED)

        goal = "voice.transcribe test speech input"
        result = asyncio.run(self.orchestrator.process_request_async(goal))

        self.assertTrue(result.success, f"Expected successful voice execution, got error: {result.warnings}")
        self.assertIn("transcripts", result.data)
        transcripts = result.data["transcripts"]
        self.assertTrue(len(transcripts) > 0)
        self.assertIn("test speech input", transcripts[0].get("transcript", ""))

    # ═════════════════════════════════════════════════════════════════════════
    #  GATE G2: Vision Grounding & Coordinate Space Invariant
    # ═════════════════════════════════════════════════════════════════════════

    def test_g2_vision_grounding_coordinates_and_bbox(self) -> None:
        """Verify UI element visual grounding returns concrete coordinates and bounding boxes."""
        self.privacy.set_device_permission(DeviceType.SCREEN_CAPTURE, PermissionState.ALLOWED)

        backend = VisionEngineBackend()
        res = backend.execute("vision.ground_element", goal="find Save Button", arguments={"description": "Save Button"})

        self.assertTrue(res.success)
        grounding = res.data.get("grounding", {})
        self.assertTrue(grounding.get("found"))
        self.assertIn("bbox", grounding)
        self.assertIn("center_coordinates", grounding)
        self.assertEqual(grounding.get("coordinate_space"), "screen_pixels")
        self.assertGreater(grounding.get("confidence", 0), 0.8)

    # ═════════════════════════════════════════════════════════════════════════
    #  GATE G3: Voice Reliability & Deterministic Degradation
    # ═════════════════════════════════════════════════════════════════════════

    def test_g3_voice_backend_fallback_and_degradation(self) -> None:
        """Verify voice backend returns explicit degraded/unavailable state when STT is empty."""
        self.privacy.set_device_permission(DeviceType.MICROPHONE, PermissionState.ALLOWED)

        backend = VoiceEngineBackend()
        # Explicit empty audio_data without test flag should return explicit degradation error (no silent mock)
        res = backend.execute("voice.transcribe", goal="voice.transcribe", arguments={"audio_data": ""})
        self.assertFalse(res.success)
        self.assertEqual(res.data.get("error"), "STT_UNAVAILABLE")

    def test_g3_voice_speech_synthesis(self) -> None:
        """Verify voice synthesis synthesizes spoken text through TTS fallback chain."""
        backend = VoiceEngineBackend()
        res = backend.execute("voice.speak", goal="speak text", arguments={"text": "System operational and secure."})

        self.assertTrue(res.success)
        self.assertIn("System operational", res.data.get("text", ""))
        self.assertIn("speaker_used", res.data)
        self.assertGreater(res.data.get("duration_seconds", 0), 0)

    # ═════════════════════════════════════════════════════════════════════════
    #  GATE G4: Device Privacy & Sensitive-Window Default-BLOCK
    # ═════════════════════════════════════════════════════════════════════════

    def test_g4_device_privacy_denied_zero_mic_capture(self) -> None:
        """Verify Denied microphone permission halts acquisition before audio capture."""
        self.privacy.set_device_permission(DeviceType.MICROPHONE, PermissionState.DENIED)

        backend = VoiceEngineBackend()
        res = backend.execute("voice.listen", goal="listen to mic", arguments={"duration_seconds": 3.0})

        self.assertFalse(res.success)
        self.assertTrue(res.data.get("blocked_by_privacy"))
        self.assertEqual(res.data.get("device"), "microphone")
        self.assertTrue(any("BLOCKED" in obs for obs in res.observations))

    def test_g4_device_privacy_denied_zero_screen_capture(self) -> None:
        """Verify Denied screen permission halts capture before screenshot API is called."""
        self.privacy.set_device_permission(DeviceType.SCREEN_CAPTURE, PermissionState.DENIED)

        backend = VisionEngineBackend()
        res = backend.execute("vision.capture", goal="capture full screen", arguments={"capture_type": "full_screen"})

        self.assertFalse(res.success)
        self.assertTrue(res.data.get("blocked_by_privacy"))
        self.assertEqual(res.data.get("device"), "screen_capture")

    def test_g4_sensitive_window_pre_capture_blocking(self) -> None:
        """Verify sensitive credential dialogs (KeePass, BitLocker, Windows Security) trigger pre-capture BLOCK."""
        self.privacy.set_device_permission(DeviceType.SCREEN_CAPTURE, PermissionState.ALLOWED)

        sensitive_cases = [
            {"window_title": "KeePass - Database.kdbx", "process_name": "KeePass.exe"},
            {"window_title": "1Password - Unlock Vault", "process_name": "1Password.exe"},
            {"window_title": "Windows Security - Enter PIN", "process_name": "CredentialUIBroker.exe"},
            {"window_title": "BitLocker Drive Encryption", "process_name": "bitlocker.exe"},
        ]

        backend = VisionEngineBackend()
        for case in sensitive_cases:
            res = backend.execute("vision.capture", goal="capture window", arguments=case)
            self.assertFalse(res.success, f"Expected capture block for sensitive window: {case}")
            self.assertTrue(res.data.get("blocked_by_privacy"))
            priv_eval = res.data.get("privacy_eval", {})
            self.assertEqual(priv_eval.get("policy"), "BLOCK")

    # ═════════════════════════════════════════════════════════════════════════
    #  GATE G5: Multimodal Memory Provenance Consolidation
    # ═════════════════════════════════════════════════════════════════════════

    def test_g5_multimodal_cognitive_memory_provenance(self) -> None:
        """Verify multimodal observations consolidate into CognitiveMemory with complete provenance."""
        engine = ConsolidationEngine()
        session_id = "sess_m22_multimodal_test"

        # Vision result
        vis_result = {
            "session_id": session_id,
            "goal": "look at screen",
            "backend": "vision_engine",
            "observations": ["Visual perception of desktop with 5 elements"],
            "data": {
                "backend": "vision_engine",
                "vision_captures": [{"capture_id": "cap_123", "window_title": "VS Code"}],
                "grounding": {"window_title": "VS Code", "bbox": [10, 10, 100, 100]},
            },
        }

        consolidated = engine.consolidate_session(
            session_id=session_id,
            goal=vis_result["goal"],
            execution_success=True,
            observations=vis_result["observations"],
            data=vis_result["data"],
        )

        self.assertTrue(len(consolidated) >= 1)
        vis_mem = next((m for m in consolidated if m.metadata.get("modality") == "vision"), None)
        self.assertIsNotNone(vis_mem)
        self.assertEqual(vis_mem.type, MemoryType.SEMANTIC)
        self.assertEqual(vis_mem.provenance.source_type, ProvenanceSource.EXECUTION_RESULT)
        self.assertEqual(vis_mem.metadata.get("device_id"), "screen_capture")
        self.assertEqual(vis_mem.metadata.get("window_title"), "VS Code")

    # ═════════════════════════════════════════════════════════════════════════
    #  GATE G6: Capability Governance & Registry
    # ═════════════════════════════════════════════════════════════════════════

    def test_g6_multimodal_capability_registry_governance(self) -> None:
        """Verify multimodal capabilities are registered with ActionRisk and typed schemas."""
        provider = MultimodalCapabilityProvider()
        caps = provider.list_capabilities()

        self.assertGreaterEqual(len(caps), 8)
        for c in caps:
            self.assertEqual(c.domain, "multimodal")
            self.assertIn(c.risk_level, (ActionRisk.LOW, ActionRisk.MEDIUM))
            self.assertTrue(len(c.permissions) > 0)
            self.assertIsNotNone(c.input_schema)
            self.assertIsNotNone(c.output_schema)

        # Ensure universal registry contains the capabilities
        reg = CapabilityRegistry.get_instance()
        self.assertIsNotNone(reg.get("vision.capture"))
        self.assertIsNotNone(reg.get("vision.describe"))
        self.assertIsNotNone(reg.get("voice.transcribe"))
        self.assertIsNotNone(reg.get("voice.speak"))


if __name__ == "__main__":
    unittest.main()
