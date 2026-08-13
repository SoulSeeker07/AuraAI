"""
Speech-to-Text Manager

Streaming Speech-to-Text with partial results support.
Enables low-latency, real-time transcription.

Primary STT engine : faster-whisper (local / offline)
Fallback STT engine: Vosk (local / offline, smaller footprint)
"""

import logging
import os
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


class STTProvider(Enum):
    """Speech-to-Text providers."""

    FASTER_WHISPER = "faster_whisper"  # faster-whisper (local / primary)
    WHISPER        = "whisper"         # openai-whisper (legacy)
    VOSK           = "vosk"            # Vosk (local / offline fallback)
    DEEPGRAM       = "deepgram"        # Deepgram (cloud)
    AZURE          = "azure"           # Azure Speech (cloud)
    GOOGLE         = "google"          # Google Speech (cloud)
    COHERE         = "cohere"
    FUTURE         = "future"


class STTSettings:
    """Configuration for STT."""

    def __init__(
        self,
        provider: "STTProvider | str" = STTProvider.FASTER_WHISPER,
        language: str = "en",
        sample_rate: int = 16000,
        model_size: str = "tiny",
        verbose: bool = False,
        chunk_size: int = 20,
        processing_delay_ms: float = 50,
        max_alternatives: int = 1,
    ):
        # Coerce string → STTProvider enum
        if isinstance(provider, str):
            prov_enum = None
            for member in STTProvider:
                if member.value == provider:
                    prov_enum = member
                    break
            if prov_enum is None:
                raise ValueError(f"Invalid STT provider string: {provider!r}")
            self.provider = prov_enum
        else:
            self.provider = provider

        self.language = language
        self.sample_rate = sample_rate
        self.model_size = model_size
        self.verbose = verbose
        self.chunk_size = chunk_size
        self.processing_delay_ms = processing_delay_ms
        self.max_alternatives = max_alternatives

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider.value,
            "language": self.language,
            "sample_rate": self.sample_rate,
            "model_size": self.model_size,
            "verbose": self.verbose,
            "chunk_size": self.chunk_size,
            "processing_delay_ms": self.processing_delay_ms,
            "max_alternatives": self.max_alternatives,
        }


class STTEngine(ABC):
    """Abstract STT engine."""

    def __init__(self, settings: STTSettings):
        self.settings = settings
        self.is_active = False
        self._stream = None
        self._partial_callback: Callable[[str, float], None] | None = None
        self._final_callback: Callable[[str, float], None] | None = None
        self._error_callback: Callable[[str], None] | None = None
        self._total_duration = 0.0

    @abstractmethod
    def initialize(self) -> bool:
        pass

    @abstractmethod
    def process_chunk(self, audio_data: bytes) -> str:
        """Process audio chunk and return partial transcript."""
        pass

    @abstractmethod
    def finalize(self) -> str:
        """Finalize transcription and return complete transcript."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset for new session."""
        pass

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        pass

    def set_callbacks(
        self,
        partial: Callable[[str, float], None],
        final: Callable[[str, float], None],
        error: Callable[[str], None],
    ) -> None:
        self._partial_callback = partial
        self._final_callback = final
        self._error_callback = error

    def _emit_partial(self, text: str, duration: float) -> None:
        if self._partial_callback:
            self._partial_callback(text, duration)

    def _emit_final(self, text: str, duration: float) -> None:
        if self._final_callback:
            self._final_callback(text, duration)

    def _emit_error(self, error: str) -> None:
        if self._error_callback:
            self._error_callback(error)


# ─────────────────────────────────────────────────────────────────────────────
#  FasterWhisperSTTEngine  (primary — local / offline)
# ─────────────────────────────────────────────────────────────────────────────

class FasterWhisperSTTEngine(STTEngine):
    """faster-whisper STT — local, offline, no API key required.

    Requires:
      - ``faster-whisper`` package (already installed).
      - Model downloaded automatically on first use from HuggingFace.

    Supported model sizes: tiny, base, small, medium, large-v2, large-v3, turbo.
    """

    def __init__(self, settings: STTSettings):
        super().__init__(settings)
        self.model = None
        self._audio_buffer: list[bytes] = []

    def initialize(self) -> bool:
        try:
            from faster_whisper import WhisperModel

            compute_type = "int8"   # safe for all CPU configs
            logger.info(
                f"Loading faster-whisper model: {self.settings.model_size} "
                f"(device=cpu, compute_type={compute_type})"
            )
            self.model = WhisperModel(
                self.settings.model_size,
                device="cpu",
                compute_type=compute_type,
            )
            self.is_active = True
            logger.info("faster-whisper STT initialized")
            return True

        except ImportError:
            logger.error("faster-whisper not installed: pip install faster-whisper")
            return False
        except Exception as e:
            logger.error(f"Error initializing faster-whisper: {e}")
            return False

    def process_chunk(self, audio_data: bytes) -> str:
        """Buffer audio chunk; returns empty string (transcription happens at finalize)."""
        if not self.is_active:
            return ""
        self._audio_buffer.append(audio_data)
        self._total_duration += len(audio_data) / (self.settings.sample_rate * 2)
        return ""

    def finalize(self) -> str:
        """Transcribe all buffered audio and return full transcript."""
        if not self.is_active or not self._audio_buffer:
            return ""

        try:
            import numpy as np

            raw = b"".join(self._audio_buffer)
            audio_np = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

            lang = self.settings.language.split("-")[0]  # "en-US" → "en"
            segments, _info = self.model.transcribe(
                audio_np,
                language=lang,
                beam_size=5,
            )
            text = " ".join(s.text.strip() for s in segments).strip()
            duration = self._total_duration

            if text:
                self._emit_final(text, duration)

            return text

        except Exception as e:
            logger.error(f"faster-whisper finalize error: {e}")
            self._emit_error(str(e))
            return ""

    def reset(self) -> None:
        self._audio_buffer.clear()
        self._total_duration = 0.0
        logger.debug("faster-whisper STT reset")

    def get_status(self) -> dict[str, Any]:
        return {
            "provider": STTProvider.FASTER_WHISPER.value,
            "is_active": self.is_active,
            "model": self.settings.model_size,
            "language": self.settings.language,
            "buffered_chunks": len(self._audio_buffer),
            "total_duration": self._total_duration,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  WhisperSTTEngine  (openai-whisper — legacy)
# ─────────────────────────────────────────────────────────────────────────────

class WhisperSTTEngine(STTEngine):
    """OpenAI Whisper STT (legacy — use FasterWhisperSTTEngine instead)."""

    def __init__(self, settings: STTSettings):
        super().__init__(settings)
        self.model = None

    def initialize(self) -> bool:
        try:
            import whisper

            self.model = whisper.load_model(self.settings.model_size)
            self.is_active = True
            logger.info(f"Whisper STT initialized with model: {self.settings.model_size}")
            return True
        except ImportError:
            logger.error("openai-whisper not installed: pip install openai-whisper")
            return False
        except Exception as e:
            logger.error(f"Error initializing Whisper: {e}")
            return False

    def process_chunk(self, audio_data: bytes) -> str:
        if not self.is_active:
            return ""
        try:
            if not self._stream:
                return ""
            result = self.model.transcribe(
                audio_data, language=self.settings.language, fp16=False
            )
            text = result["text"].strip()
            self._total_duration += len(audio_data) / self.settings.sample_rate / 2
            self._emit_partial(text, self._total_duration)
            return text
        except Exception as e:
            logger.error(f"Whisper chunk error: {e}")
            self._emit_error(str(e))
            return ""

    def finalize(self) -> str:
        if not self.is_active:
            return ""
        try:
            result = self.model.transcribe(
                self._stream, language=self.settings.language, fp16=False
            )
            text = result["text"].strip()
            self._emit_final(text, self._total_duration)
            return text
        except Exception as e:
            logger.error(f"Whisper finalize error: {e}")
            self._emit_error(str(e))
            return ""

    def reset(self) -> None:
        self._stream = None
        self._total_duration = 0.0
        logger.debug("Whisper STT reset")

    def get_status(self) -> dict[str, Any]:
        return {
            "provider": STTProvider.WHISPER.value,
            "is_active": self.is_active,
            "model": self.settings.model_size,
            "language": self.settings.language,
            "total_duration": self._total_duration,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  VoskSTTEngine  (offline fallback)
# ─────────────────────────────────────────────────────────────────────────────

class VoskSTTEngine(STTEngine):
    """Vosk STT — offline fallback, lightweight, no internet required.

    Requires:
      - ``vosk`` package (already installed).
      - A Vosk model directory. Path set via VOSK_MODEL_PATH in .env.
    """

    def __init__(self, settings: STTSettings):
        super().__init__(settings)
        self.model = None
        self.recognizer = None

    def _get_model_path(self) -> str | None:
        return _resolve_model_path(os.getenv("VOSK_MODEL_PATH"))

    def initialize(self) -> bool:
        try:
            import vosk

            model_path = self._get_model_path()
            if not model_path:
                logger.error(
                    "Vosk: no model path. Set VOSK_MODEL_PATH in .env. "
                    "Run scripts/setup_voice_models.py to download."
                )
                return False

            if not Path(model_path).exists():
                logger.error(f"Vosk model directory not found: {model_path}")
                return False

            vosk.SetLogLevel(-1)
            self.model = vosk.Model(model_path)
            self.recognizer = vosk.KaldiRecognizer(self.model, self.settings.sample_rate)
            self._stream = ""
            self.is_active = True
            logger.info("Vosk STT initialized")
            return True

        except ImportError:
            logger.error("vosk not installed: pip install vosk")
            return False
        except Exception as e:
            logger.error(f"Error initializing Vosk: {e}")
            return False

    def process_chunk(self, audio_data: bytes) -> str:
        if not self.is_active or not self.recognizer:
            return ""
        try:
            if self.recognizer.AcceptWaveform(audio_data):
                import json
                result = json.loads(self.recognizer.Result())
                text = result.get("text", "")
                if text:
                    self._stream = (self._stream or "") + " " + text
                    duration = self._total_duration + len(audio_data) / self.settings.sample_rate / 2
                    self._emit_partial(self._stream.strip(), duration)
                    return text
            return ""
        except Exception as e:
            logger.error(f"Vosk chunk error: {e}")
            self._emit_error(str(e))
            return ""

    def finalize(self) -> str:
        if not self.is_active or not self.recognizer:
            return ""
        try:
            import json
            result = json.loads(self.recognizer.FinalResult())
            text = result.get("text", "")
            full = ((self._stream or "") + " " + text).strip()
            duration = self._total_duration
            if full:
                self._emit_final(full, duration)
            return full
        except Exception as e:
            logger.error(f"Vosk finalize error: {e}")
            self._emit_error(str(e))
            return ""

    def reset(self) -> None:
        self._stream = ""
        self._total_duration = 0.0
        if self.model:
            import vosk
            self.recognizer = vosk.KaldiRecognizer(self.model, self.settings.sample_rate)
        logger.debug("Vosk STT reset")

    def get_status(self) -> dict[str, Any]:
        return {
            "provider": STTProvider.VOSK.value,
            "is_active": self.is_active,
            "sample_rate": self.settings.sample_rate,
            "model_path": self._get_model_path(),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  DeepgramSTTEngine  (cloud — optional)
# ─────────────────────────────────────────────────────────────────────────────

class DeepgramSTTEngine(STTEngine):
    """Deepgram STT (cloud)."""

    def __init__(self, settings: STTSettings):
        super().__init__(settings)
        self.deepgram = None

    def initialize(self) -> bool:
        try:
            import deepgram

            key = os.getenv("DEEPGRAM_API_KEY")
            if not key:
                logger.error("No DEEPGRAM_API_KEY in environment")
                return False
            self.deepgram = deepgram.DeepgramClient(key)
            self.is_active = True
            logger.info("Deepgram STT initialized")
            return True
        except ImportError:
            logger.error("deepgram not installed")
            return False
        except Exception as e:
            logger.error(f"Error initializing Deepgram: {e}")
            return False

    def process_chunk(self, audio_data: bytes) -> str:
        return ""

    def finalize(self) -> str:
        return ""

    def reset(self) -> None:
        self._stream = None
        self._total_duration = 0.0

    def get_status(self) -> dict[str, Any]:
        return {
            "provider": STTProvider.DEEPGRAM.value,
            "is_active": self.is_active,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  STTManager  (orchestrator)
# ─────────────────────────────────────────────────────────────────────────────

class STTManager:
    """Streaming STT Manager."""

    def __init__(self, settings: STTSettings):
        self.settings = settings
        self.engine: STTEngine | None = None
        self._stream_buffer = bytearray()

    def initialize(self) -> bool:
        """Initialize STT engine."""
        if self.engine:
            return self.engine.is_active

        try:
            p = self.settings.provider
            if p == STTProvider.FASTER_WHISPER:
                self.engine = FasterWhisperSTTEngine(self.settings)
            elif p == STTProvider.WHISPER:
                self.engine = WhisperSTTEngine(self.settings)
            elif p == STTProvider.VOSK:
                self.engine = VoskSTTEngine(self.settings)
            elif p == STTProvider.DEEPGRAM:
                self.engine = DeepgramSTTEngine(self.settings)
            else:
                logger.error(f"Unsupported STT provider: {p}")
                return False

            return self.engine.initialize()

        except Exception as e:
            logger.error(f"Error initializing STT manager: {e}")
            return False

    def process_audio(self, audio_data: bytes) -> str:
        """Process audio chunk."""
        if not self.engine or not self.engine.is_active:
            return ""
        self._stream_buffer.extend(audio_data)
        try:
            return self.engine.process_chunk(audio_data)
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            return ""

    def finalize(self) -> str:
        """Finalize transcription."""
        if not self.engine or not self.engine.is_active:
            return ""
        try:
            return self.engine.finalize()
        except Exception as e:
            logger.error(f"Error finalizing STT: {e}")
            return ""

    def reset(self) -> None:
        """Reset for new session."""
        if self.engine:
            self.engine.reset()
        self._stream_buffer.clear()
        logger.debug("STT manager reset")

    def get_status(self) -> dict[str, Any]:
        """Get current status."""
        if self.engine:
            return self.engine.get_status()
        return {"provider": self.settings.provider.value, "is_active": False}
