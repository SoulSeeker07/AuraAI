"""
Text-to-Speech Manager

Streaming Text-to-Speech with low-latency, real-time playback.
Enables responsive voice interactions.

Primary TTS engine : Piper (local / offline)
Fallback TTS engine: Edge-TTS (online / Microsoft)
"""

import asyncio
import logging
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Project root — used to resolve relative model paths from .env / config.
_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]


def _resolve_model_path(raw: str | None) -> str | None:
    """Return an absolute path string, resolving relative paths from project root."""
    if not raw:
        return None
    p = Path(raw)
    if p.is_absolute():
        return str(p)
    resolved = _PROJECT_ROOT / p
    return str(resolved)


class TTSSpeaker(Enum):
    """Text-to-Speech speakers."""

    PIPER    = "piper"     # Piper TTS (local / primary)
    EDGE_TTS = "edge_tts"  # Microsoft Edge TTS (online / fallback)
    AZURE_TTS   = "azure_tts"
    GOOGLE_TTS  = "google_tts"
    LOCALLY     = "locally"


class TTSSettings:
    """Configuration for TTS."""

    def __init__(
        self,
        speaker: "TTSSpeaker | str" = TTSSpeaker.PIPER,
        voice: str | None = None,
        rate: float = 1.0,
        pitch: float = 1.0,
        volume: float = 1.0,
        streaming: bool = True,
        interruptible: bool = True,
        fallback_speaker: "TTSSpeaker | str | None" = None,
    ):
        # Coerce string to TTSSpeaker enum
        if isinstance(speaker, str):
            speaker_enum = None
            for member in TTSSpeaker:
                if member.value == speaker:
                    speaker_enum = member
                    break
            if speaker_enum is None:
                raise ValueError(f"Invalid speaker string: {speaker!r}")
            self.speaker = speaker_enum
        else:
            self.speaker = speaker

        # Coerce fallback_speaker string to TTSSpeaker enum if provided
        if isinstance(fallback_speaker, str):
            fallback_enum = None
            for member in TTSSpeaker:
                if member.value == fallback_speaker:
                    fallback_enum = member
                    break
            if fallback_enum is None:
                raise ValueError(f"Invalid fallback_speaker string: {fallback_speaker!r}")
            self.fallback_speaker = fallback_enum
        else:
            self.fallback_speaker = fallback_speaker

        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        self.streaming = streaming
        self.interruptible = interruptible

    def to_dict(self) -> dict[str, Any]:
        return {
            "speaker": self.speaker.value,
            "voice": self.voice,
            "rate": self.rate,
            "pitch": self.pitch,
            "volume": self.volume,
            "streaming": self.streaming,
            "interruptible": self.interruptible,
            "fallback_speaker": (
                self.fallback_speaker.value if self.fallback_speaker else None
            ),
        }


class TTSEngine(ABC):
    """Abstract TTS engine."""

    def __init__(self, settings: TTSSettings):
        self.settings = settings
        self.is_active = False
        self._is_playing = False
        self._stream: list[str] = []
        self._playback_complete_callback: Callable[[], None] | None = None
        self._interrupt_callback: Callable[[], None] | None = None

    @abstractmethod
    def initialize(self) -> bool:
        pass

    @abstractmethod
    def add_text(self, text: str, interruptible: bool = True) -> bool:
        """Add text to speech queue."""
        pass

    @abstractmethod
    def speak(self) -> bool:
        """Start speaking the queued text."""
        pass

    @abstractmethod
    def stop(self) -> bool:
        """Stop current speech."""
        pass

    @abstractmethod
    def is_playing(self) -> bool:
        """Check if currently speaking."""
        pass

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        pass

    def set_callbacks(
        self, complete: Callable[[], None], interrupt: Callable[[], None]
    ) -> None:
        self._playback_complete_callback = complete
        self._interrupt_callback = interrupt

    def _emit_complete(self) -> None:
        if self._playback_complete_callback:
            self._playback_complete_callback()

    def _emit_interrupt(self) -> None:
        if self._interrupt_callback:
            self._interrupt_callback()


# ─────────────────────────────────────────────────────────────────────────────
#  Piper TTS  (primary — local / offline)
# ─────────────────────────────────────────────────────────────────────────────

class PiperTTSEngine(TTSEngine):
    """Piper TTS — local, offline, no API key required.

    Requires:
      - ``piper-tts`` package (``pip install piper-tts``)
      - A Piper voice model (.onnx + .onnx.json).
        Path configured via PIPER_MODEL_PATH in .env (relative to project root).
    """

    def __init__(self, settings: TTSSettings):
        super().__init__(settings)
        self.voice = None  # piper.voice.PiperVoice instance

    # ── internal helpers ───────────────────────────────────────────────────

    def _get_model_path(self) -> str | None:
        """Return resolved absolute path to .onnx model, or None."""
        import os
        raw = self.settings.voice or os.getenv("PIPER_MODEL_PATH")
        return _resolve_model_path(raw)

    # ── TTSEngine interface ────────────────────────────────────────────────

    def initialize(self) -> bool:
        try:
            from piper.voice import PiperVoice  # piper-tts 1.6+

            model_path = self._get_model_path()
            if not model_path:
                logger.error(
                    "Piper: no model path. Set PIPER_MODEL_PATH in .env or "
                    "pass voice=<path> in TTSSettings."
                )
                return False

            if not Path(model_path).exists():
                logger.error(f"Piper model not found: {model_path}")
                return False

            logger.info(f"Loading Piper model: {model_path}")
            self.voice = PiperVoice.load(model_path)
            self.is_active = True
            logger.info("Piper TTS initialized")
            return True

        except ImportError:
            logger.error("piper-tts not installed: pip install piper-tts")
            return False
        except Exception as e:
            logger.error(f"Error initializing Piper TTS: {e}")
            return False

    def add_text(self, text: str, interruptible: bool = True) -> bool:
        if not self.is_active:
            return False
        self._stream.append(text)
        return True

    def speak(self) -> bool:
        if not self.is_active or not self._stream:
            return False
        if self._is_playing:
            return True

        text = " ".join(self._stream)
        self._stream.clear()
        self._is_playing = True

        def _run():
            try:
                import numpy as np
                import sounddevice as sd

                sample_rate = self.voice.config.sample_rate
                chunks: list[bytes] = []
                for audio_chunk in self.voice.synthesize(text):
                    chunks.append(audio_chunk.audio_int16_bytes)

                if chunks:
                    raw = b"".join(chunks)
                    audio_np = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                    sd.play(audio_np, samplerate=sample_rate)
                    sd.wait()

                self._emit_complete()
            except Exception as e:
                logger.error(f"Piper speak error: {e}")
            finally:
                self._is_playing = False

        threading.Thread(target=_run, daemon=True).start()
        return True

    def stop(self) -> bool:
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
        self._stream.clear()
        self._is_playing = False
        self._emit_interrupt()
        return True

    def is_playing(self) -> bool:
        return self._is_playing

    def get_status(self) -> dict[str, Any]:
        return {
            "speaker": self.settings.speaker.value,
            "is_active": self.is_active,
            "is_playing": self._is_playing,
            "model": self._get_model_path(),
            "chunks": len(self._stream),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  Edge TTS  (fallback — online / Microsoft)
# ─────────────────────────────────────────────────────────────────────────────

class EdgeTTSEngine(TTSEngine):
    """Microsoft Edge TTS — online fallback, no subscription required."""

    def __init__(self, settings: TTSSettings):
        super().__init__(settings)
        self.engine = None

    def initialize(self) -> bool:
        try:
            import edge_tts  # noqa: F401

            self.is_active = True
            logger.info("Edge TTS initialized")
            return True
        except ImportError:
            logger.error("edge-tts not installed: pip install edge-tts")
            return False
        except Exception as e:
            logger.error(f"Error initializing Edge TTS: {e}")
            return False

    def add_text(self, text: str, interruptible: bool = True) -> bool:
        if not self.is_active:
            return False
        self._stream.append(text)
        return True

    def speak(self) -> bool:
        if not self.is_active or not self._stream:
            return False

        try:
            import asyncio
            import edge_tts

            if not self._is_playing:
                self._is_playing = True

                voice_name = self.settings.voice or "en-US-AriaNeural"
                communicate = edge_tts.Communicate(
                    self._stream[0],
                    voice_name,
                    rate=f"{(self.settings.rate - 1) * 100:+.0f}%",
                    volume=f"{(self.settings.volume - 1) * 100:+.0f}%",
                )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def _speak():
                    try:
                        import io
                        import sounddevice as sd
                        import soundfile as sf

                        audio_buf = io.BytesIO()
                        async for chunk in communicate.stream():
                            if chunk["type"] == "audio":
                                audio_buf.write(chunk["data"])

                        audio_buf.seek(0)
                        data, samplerate = sf.read(audio_buf)
                        sd.play(data, samplerate=samplerate)
                        sd.wait()
                        self._emit_complete()
                    except asyncio.CancelledError:
                        logger.info("Edge TTS speech interrupted")
                        self._emit_interrupt()
                    finally:
                        self._is_playing = False

                def _run():
                    loop.run_until_complete(_speak())
                    loop.close()

                threading.Thread(target=_run, daemon=True).start()

            return True

        except Exception as e:
            logger.error(f"Edge TTS speak error: {e}")
            return False

    def stop(self) -> bool:
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
        self._stream.clear()
        self._is_playing = False
        self._emit_interrupt()
        return True

    def is_playing(self) -> bool:
        return self._is_playing

    def get_status(self) -> dict[str, Any]:
        return {
            "speaker": self.settings.speaker.value,
            "is_active": self.is_active,
            "is_playing": self._is_playing,
            "chunks": len(self._stream),
            "voice": self.settings.voice,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  TTSManger  (orchestrator)
# ─────────────────────────────────────────────────────────────────────────────

class TTSManger:
    """Streaming TTS Manager.

    Lifecycle
    ---------
    Lazy initialization: the underlying engine is created on the first call to
    :meth:`add_text`. Callers do not need to call :meth:`initialize` explicitly.
    Explicit :meth:`initialize` is idempotent — safe to call multiple times.

    Callbacks
    ---------
    Register callbacks via :meth:`set_callbacks` at any point — before or after
    the engine is created. They are stored and wired to the engine whenever it
    becomes available.
    """

    def __init__(self, settings: TTSSettings):
        self.settings = settings
        self.engine: TTSEngine | None = None
        # Pending callbacks stored so they survive lazy initialization.
        self._pending_complete_callback: Callable[[], None] | None = None
        self._pending_interrupt_callback: Callable[[], None] | None = None

    def set_callbacks(
        self,
        complete: Callable[[], None],
        interrupt: Callable[[], None],
    ) -> None:
        """Register playback-complete and interrupt callbacks.

        Safe to call before or after the engine is created — callbacks are
        stored and applied to the engine whenever it becomes available.
        """
        self._pending_complete_callback = complete
        self._pending_interrupt_callback = interrupt
        if self.engine:
            self.engine.set_callbacks(complete, interrupt)

    def initialize(self) -> bool:
        """Initialize TTS engine. Idempotent — safe to call multiple times."""
        if self.engine and self.engine.is_active:
            return True

        try:
            speaker_enum = self._resolve_speaker()
            if speaker_enum is None:
                return False

            if speaker_enum == TTSSpeaker.PIPER:
                self.engine = PiperTTSEngine(self.settings)
            elif speaker_enum == TTSSpeaker.EDGE_TTS:
                self.engine = EdgeTTSEngine(self.settings)
            else:
                logger.error(f"Unsupported speaker: {speaker_enum}")
                return False

            ok = self.engine.initialize()
            if ok and self._pending_complete_callback:
                self.engine.set_callbacks(
                    self._pending_complete_callback,
                    self._pending_interrupt_callback,
                )
            return ok

        except Exception as e:
            logger.error(f"Error initializing TTS manager: {e}")
            return False

    def _resolve_speaker(self) -> TTSSpeaker | None:
        if isinstance(self.settings.speaker, str):
            for member in TTSSpeaker:
                if member.value == self.settings.speaker:
                    return member
            logger.error(f"Unsupported speaker string: {self.settings.speaker!r}")
            return None
        return self.settings.speaker

    def add_text(self, text: str) -> bool:
        """Add text to speech queue.

        Performs lazy initialization if the engine has not been created yet,
        so callers do not need to call :meth:`initialize` explicitly.
        """
        if not self.engine:
            logger.debug("TTS engine not yet initialized — attempting lazy init")
            if not self.initialize():
                logger.error("TTS lazy initialization failed; cannot add text")
                return False

        return self.engine.add_text(text)

    def speak(self) -> bool:
        """Start speaking."""
        if not self.engine:
            return False
        return self.engine.speak()

    def stop(self) -> bool:
        """Stop speaking."""
        if not self.engine:
            return False
        return self.engine.stop()

    def is_playing(self) -> bool:
        """Check if speaking."""
        if not self.engine:
            return False
        return self.engine.is_playing()

    def get_status(self) -> dict[str, Any]:
        """Get current status."""
        if self.engine:
            return self.engine.get_status()
        return {"speaker": self.settings.speaker.value, "is_active": False}
