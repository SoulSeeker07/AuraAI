"""
Multimodal Capability Provider (Voice & Vision)
Location: src/core/capabilities/providers/multimodal_provider.py

Exposes typed capability descriptors and ActionRisk governance for:
- Screen perception, OCR, and coordinate grounding (Vision).
- Speech audio acquisition, STT, and TTS synthesis (Voice).
"""

from __future__ import annotations

from core.capabilities.models import Capability
from core.capabilities.provider import ICapabilityProvider
from core.orchestration.autonomy_mode import ActionRisk


class MultimodalCapabilityProvider(ICapabilityProvider):
    """Provider for vision perception, UI coordinate grounding, speech STT, and voice TTS."""

    DOMAIN = "multimodal"

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = self._build_capabilities()

    @property
    def domain(self) -> str:
        return self.DOMAIN

    def _build_capabilities(self) -> dict[str, Capability]:
        caps = [
            # ── Vision Capabilities ─────────────────────────────────────────
            Capability(
                name="vision.capture",
                domain=self.DOMAIN,
                description="Capture a screen, monitor, window, or region frame with pre-capture privacy verification.",
                category="perception",
                input_schema={
                    "type": "object",
                    "properties": {
                        "capture_type": {"type": "string", "enum": ["full_screen", "active_window", "active_monitor", "region"], "default": "full_screen"},
                        "window_title": {"type": "string"},
                        "region": {"type": "array", "items": {"type": "integer"}},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "image_path": {"type": "string"},
                        "width": {"type": "integer"},
                        "height": {"type": "integer"},
                        "format": {"type": "string"},
                        "privacy_status": {"type": "string"},
                    },
                },
                risk_level=ActionRisk.LOW,
                permissions=["device:screen_capture"],
                execution_backend="vision_engine",
                is_live=True,
                availability="local",
                requires=[],
                verifies=[],
                tags=["vision", "screen", "capture", "multimodal"],
            ),
            Capability(
                name="vision.describe",
                domain=self.DOMAIN,
                description="Analyze visual desktop contents, active window layouts, and UI hierarchy.",
                category="perception",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "image_path": {"type": "string"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "elements_count": {"type": "integer"},
                        "confidence": {"type": "number"},
                    },
                },
                risk_level=ActionRisk.LOW,
                permissions=["device:screen_capture"],
                execution_backend="vision_engine",
                is_live=True,
                availability="local",
                requires=["vision.capture"],
                verifies=[],
                tags=["vision", "describe", "analysis", "multimodal"],
            ),
            Capability(
                name="vision.ocr",
                domain=self.DOMAIN,
                description="Extract text blocks, bounding boxes, and coordinate anchors from visual screen captures.",
                category="perception",
                input_schema={
                    "type": "object",
                    "properties": {
                        "image_path": {"type": "string"},
                        "target_text": {"type": "string"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "text_blocks": {"type": "array"},
                        "confidence": {"type": "number"},
                    },
                },
                risk_level=ActionRisk.LOW,
                permissions=["device:screen_capture"],
                execution_backend="vision_engine",
                is_live=True,
                availability="local",
                requires=["vision.capture"],
                verifies=[],
                tags=["vision", "ocr", "text", "multimodal"],
            ),
            Capability(
                name="vision.ground_element",
                domain=self.DOMAIN,
                description="Ground target UI elements to specific screen/window coordinates and bounding boxes.",
                category="grounding",
                input_schema={
                    "type": "object",
                    "required": ["description"],
                    "properties": {
                        "description": {"type": "string"},
                        "target_type": {"type": "string"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "found": {"type": "boolean"},
                        "coordinates": {"type": "object"},
                        "bbox": {"type": "array"},
                        "window_title": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                },
                risk_level=ActionRisk.LOW,
                permissions=["device:screen_capture"],
                execution_backend="vision_engine",
                is_live=True,
                availability="local",
                requires=["vision.capture"],
                verifies=[],
                tags=["vision", "grounding", "coordinates", "multimodal"],
            ),

            # ── Voice Capabilities ──────────────────────────────────────────
            Capability(
                name="voice.listen",
                domain=self.DOMAIN,
                description="Acquire microphone audio stream with pre-capture privacy policy verification.",
                category="audio_input",
                input_schema={
                    "type": "object",
                    "properties": {
                        "duration_seconds": {"type": "number", "default": 5.0},
                        "sample_rate": {"type": "integer", "default": 16000},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "audio_bytes_length": {"type": "integer"},
                        "duration": {"type": "number"},
                        "privacy_status": {"type": "string"},
                    },
                },
                risk_level=ActionRisk.LOW,
                permissions=["device:microphone"],
                execution_backend="voice_engine",
                is_live=True,
                availability="local",
                requires=[],
                verifies=[],
                tags=["voice", "audio", "microphone", "multimodal"],
            ),
            Capability(
                name="voice.transcribe",
                domain=self.DOMAIN,
                description="Transcribe speech audio into structured text using STT with resilient fallbacks.",
                category="audio_input",
                input_schema={
                    "type": "object",
                    "properties": {
                        "audio_data": {"type": "string"},
                        "language": {"type": "string", "default": "en"},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "transcript": {"type": "string"},
                        "provider_used": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                },
                risk_level=ActionRisk.LOW,
                permissions=["device:microphone"],
                execution_backend="voice_engine",
                is_live=True,
                availability="local",
                requires=["voice.listen"],
                verifies=[],
                tags=["voice", "stt", "transcribe", "multimodal"],
            ),
            Capability(
                name="voice.speak",
                domain=self.DOMAIN,
                description="Synthesize spoken response to user using configured TTS engine.",
                category="audio_output",
                input_schema={
                    "type": "object",
                    "required": ["text"],
                    "properties": {
                        "text": {"type": "string"},
                        "speaker": {"type": "string"},
                        "rate": {"type": "number", "default": 1.0},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "spoken": {"type": "boolean"},
                        "speaker_used": {"type": "string"},
                        "duration_seconds": {"type": "number"},
                    },
                },
                risk_level=ActionRisk.LOW,  # Spoken response / output modality
                permissions=["device:speaker"],
                execution_backend="voice_engine",
                is_live=True,
                availability="local",
                requires=[],
                verifies=[],
                tags=["voice", "tts", "speak", "multimodal"],
            ),
            Capability(
                name="voice.process_turn",
                domain=self.DOMAIN,
                description="Process full conversational voice turn (Listen -> Transcribe -> Orchestrate -> Speak).",
                category="interaction",
                input_schema={
                    "type": "object",
                    "properties": {
                        "audio_input": {"type": "string"},
                        "timeout": {"type": "number", "default": 10.0},
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "user_transcript": {"type": "string"},
                        "assistant_response": {"type": "string"},
                        "execution_success": {"type": "boolean"},
                    },
                },
                risk_level=ActionRisk.LOW,
                permissions=["device:microphone", "device:speaker"],
                execution_backend="voice_engine",
                is_live=True,
                availability="local",
                requires=["voice.listen", "voice.transcribe", "voice.speak"],
                verifies=[],
                tags=["voice", "conversation", "multimodal"],
            ),
        ]

        return {c.name: c for c in caps}

    def list_capabilities(self) -> list[Capability]:
        return list(self._capabilities.values())

    def get_capability(self, name: str) -> Capability | None:
        return self._capabilities.get(name)
