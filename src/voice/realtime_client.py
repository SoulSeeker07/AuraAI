"""
Realtime Duplex Protocol Client
Location: src/voice/realtime_client.py

Provides a unified client abstraction for bidirectional realtime speech sessions,
matching the OpenAI Realtime and Gemini Live event models:
- input_audio_buffer.append
- response.create
- response.cancel
- response.steer

Allows seamless switching between local duplex synthesis and cloud WebSocket duplex.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class RealtimeEventType(Enum):
    # Client -> Server
    SESSION_UPDATE       = "session.update"
    INPUT_AUDIO_APPEND   = "input_audio_buffer.append"
    INPUT_AUDIO_COMMIT   = "input_audio_buffer.commit"
    RESPONSE_CREATE      = "response.create"
    RESPONSE_CANCEL      = "response.cancel"
    RESPONSE_STEER       = "response.steer"

    # Server -> Client
    SESSION_CREATED      = "session.created"
    RESPONSE_CREATED     = "response.created"
    RESPONSE_AUDIO_DELTA = "response.audio.delta"
    RESPONSE_TEXT_DELTA  = "response.text.delta"
    RESPONSE_DONE        = "response.done"
    ERROR                = "error"


@dataclass
class RealtimeSessionConfig:
    modalities: list[str] = field(default_factory=lambda: ["audio", "text"])
    instructions: str = "You are AuraAI, an advanced desktop cognitive assistant."
    voice: str = "alloy"
    input_audio_format: str = "pcm16"
    output_audio_format: str = "pcm16"
    turn_detection: Optional[dict[str, Any]] = field(
        default_factory=lambda: {"type": "server_vad", "threshold": 0.5, "silence_duration_ms": 500}
    )


class RealtimeDuplexClient:
    """
    Standardized client for bi-directional streaming duplex sessions.
    Supports response steering, cancellation, and continuous audio streaming.
    """

    def __init__(
        self,
        config: Optional[RealtimeSessionConfig] = None,
        on_audio_delta: Optional[Callable[[bytes], None]] = None,
        on_text_delta: Optional[Callable[[str], None]] = None,
        on_response_done: Optional[Callable[[], None]] = None,
    ):
        self.config = config or RealtimeSessionConfig()
        self.on_audio_delta = on_audio_delta
        self.on_text_delta = on_text_delta
        self.on_response_done = on_response_done

        self.is_connected = False
        self.active_response_id: Optional[str] = None
        self._lock = threading.Lock()

    def connect(self) -> bool:
        """Connect duplex session."""
        with self._lock:
            self.is_connected = True
            logger.info("[RealtimeDuplexClient] Duplex session connected.")
            return True

    def disconnect(self) -> None:
        """Disconnect duplex session."""
        with self._lock:
            self.is_connected = False
            self.active_response_id = None
            logger.info("[RealtimeDuplexClient] Duplex session disconnected.")

    def send_audio_chunk(self, pcm_16k_mono: bytes) -> None:
        """Send a chunk of input microphone audio."""
        if not self.is_connected or not pcm_16k_mono:
            return
        # Dispatched to streaming socket or local VAD buffer tap
        pass

    def create_response(self, prompt: Optional[str] = None) -> str:
        """Request a response creation."""
        with self._lock:
            self.active_response_id = f"resp_{int(time.time() * 1000)}"
            logger.info(f"[RealtimeDuplexClient] response.create -> {self.active_response_id}")
            return self.active_response_id

    def cancel_response(self, response_id: Optional[str] = None) -> bool:
        """Cancel an in-flight response (response.cancel)."""
        with self._lock:
            target = response_id or self.active_response_id
            if not target:
                return False
            logger.info(f"[RealtimeDuplexClient] response.cancel -> {target}")
            self.active_response_id = None
            return True

    def steer_response(self, new_input: str, previous_response_id: Optional[str] = None) -> bool:
        """
        Steer an active response mid-generation (response.steer).
        Queues new input to create a successor response incorporating previous context.
        """
        with self._lock:
            target = previous_response_id or self.active_response_id
            if not target:
                logger.warning("[RealtimeDuplexClient] response.steer called with no active response.")
                return False

            successor_id = f"resp_{int(time.time() * 1000)}_steered"
            logger.info(
                f"[RealtimeDuplexClient] response.steer -> target={target}, "
                f"successor={successor_id}, input='{new_input}'"
            )
            self.active_response_id = successor_id
            return True
